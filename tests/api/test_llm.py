import json

import httpx
import pytest

from sera.api.config import Config
from sera.api.llm import (
    ClienteComFallback,
    ClienteOpenAICompat,
    Delta,
    ErroDoProvedor,
    Ferramenta,
    Fim,
)

pytestmark = pytest.mark.anyio

SSE = (
    b'data: {"choices":[{"delta":{"content":"Ol\xc3\xa1"}}]}\n\n'
    b'data: {"choices":[{"delta":{"content":"!"}}]}\n\n'
    b'data: {"choices":[],"usage":{"prompt_tokens":3,'
    b'"completion_tokens":2,"total_tokens":5}}\n\n'
    b"data: [DONE]\n\n"
)


def _config() -> Config:
    return Config(
        llm_base_url="http://fake.local/v1",
        llm_model="modelo-fake",
    )


async def _coletar(cliente: ClienteOpenAICompat):
    return [
        evento
        async for evento in cliente.stream(
            [{"role": "user", "content": "oi"}],
            temperatura=0.5,
            max_tokens=8,
        )
    ]


@pytest.mark.parametrize(
    ("base", "esperado", "incompleta"),
    [
        (
            "https://host/v1",
            "https://host/v1/chat/completions",
            False,
        ),
        (
            "https://host/inference/openai/v1/",
            "https://host/inference/openai/v1/chat/completions",
            False,
        ),
        (
            "https://host/v1/chat/completions",
            "https://host/v1/chat/completions",
            False,
        ),
        (
            "https://host/inference/openai",
            "https://host/inference/openai/chat/completions",
            True,
        ),
    ],
)
def test_resolve_url_chat(base, esperado, incompleta):
    config = Config(llm_base_url=base)
    assert config.url_chat == esperado
    assert config.base_incompleta is incompleta


@pytest.mark.parametrize("base", ["", "ftp://host/v1", "host/v1"])
def test_recusa_base_url_invalida(base):
    with pytest.raises(ValueError, match="llm_base_url"):
        Config(llm_base_url=base)


async def test_parseia_sse_e_uso():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://fake.local/v1/chat/completions"
        assert request.headers["content-type"] == "application/json"
        assert json.loads(request.read())["model"] == "modelo-fake"
        return httpx.Response(
            200,
            content=SSE,
            headers={"content-type": "text/event-stream"},
        )

    cliente = ClienteOpenAICompat(
        _config(), transporte=httpx.MockTransport(handler)
    )
    eventos = await _coletar(cliente)

    assert [e.texto for e in eventos if isinstance(e, Delta)] == ["Olá", "!"]
    fim = eventos[-1]
    assert isinstance(fim, Fim)
    assert fim.uso is not None
    assert fim.uso.total_tokens == 5


async def test_aceita_resposta_json_quando_provedor_ignora_stream():
    corpo = {
        "choices": [{"message": {"content": "Olá inteiro"}}],
        "usage": {
            "prompt_tokens": 1,
            "completion_tokens": 2,
            "total_tokens": 3,
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.read())["stream"] is True
        return httpx.Response(200, json=corpo)

    cliente = ClienteOpenAICompat(
        _config(), transporte=httpx.MockTransport(handler)
    )
    eventos = await _coletar(cliente)

    assert [e.texto for e in eventos if isinstance(e, Delta)] == ["Olá inteiro"]
    fim = eventos[-1]
    assert isinstance(fim, Fim)
    assert fim.uso is not None
    assert fim.uso.total_tokens == 3


async def test_faz_fallback_quando_stream_options_e_rejeitado():
    corpos: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        corpo = json.loads(request.read())
        corpos.append(corpo)
        if "stream_options" in corpo:
            return httpx.Response(
                400, content=b'{"error":"unknown field stream_options"}'
            )
        return httpx.Response(200, content=SSE)

    cliente = ClienteOpenAICompat(
        _config(), transporte=httpx.MockTransport(handler)
    )
    eventos = await _coletar(cliente)

    assert len(corpos) == 2
    assert "stream_options" in corpos[0]
    assert "stream_options" not in corpos[1]
    assert [e.texto for e in eventos if isinstance(e, Delta)] == ["Olá", "!"]


async def test_retenta_5xx_antes_do_primeiro_token():
    chamadas = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal chamadas
        chamadas += 1
        if chamadas == 1:
            return httpx.Response(500, content=b"boom")
        return httpx.Response(200, content=SSE)

    cliente = ClienteOpenAICompat(
        _config(), transporte=httpx.MockTransport(handler)
    )
    eventos = await _coletar(cliente)

    assert chamadas == 2
    assert [e.texto for e in eventos if isinstance(e, Delta)] == ["Olá", "!"]


async def test_erro_http_nao_retentavel_vira_erro_do_provedor():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, content=b"sem chave")

    cliente = ClienteOpenAICompat(
        _config(), transporte=httpx.MockTransport(handler)
    )
    with pytest.raises(ErroDoProvedor) as capturado:
        await _coletar(cliente)
    assert capturado.value.status == 401
    assert capturado.value.retentavel is False


async def test_timeout_de_leitura_nao_retenta():
    chamadas = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal chamadas
        chamadas += 1
        raise httpx.ReadTimeout("sem resposta")

    cliente = ClienteOpenAICompat(
        _config(), transporte=httpx.MockTransport(handler)
    )
    with pytest.raises(ErroDoProvedor) as capturado:
        await _coletar(cliente)

    assert capturado.value.codigo == "timeout"
    assert chamadas == 1


async def test_parseia_tool_calls_fragmentados():
    def linha(dados: dict) -> str:
        return f"data: {json.dumps(dados, ensure_ascii=False)}\n\n"

    sse = (
        linha(
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_1",
                                    "function": {
                                        "name": "pesquisar_web",
                                        "arguments": '{"cons',
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        )
        + linha(
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {
                                        "arguments": 'ulta": "dólar"}',
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        )
        + linha(
            {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}
        )
        + "data: [DONE]\n\n"
    ).encode()

    def handler(request: httpx.Request) -> httpx.Response:
        corpo = json.loads(request.read())
        assert corpo["tools"][0]["function"]["name"] == "pesquisar_web"
        return httpx.Response(
            200, content=sse, headers={"content-type": "text/event-stream"}
        )

    ferramenta = {
        "type": "function",
        "function": {
            "name": "pesquisar_web",
            "parameters": {"type": "object"},
        },
    }
    cliente = ClienteOpenAICompat(
        _config(), transporte=httpx.MockTransport(handler)
    )
    eventos = [
        evento
        async for evento in cliente.stream(
            [{"role": "user", "content": "oi"}],
            temperatura=0.5,
            max_tokens=8,
            ferramentas=[ferramenta],
        )
    ]

    chamadas = next(e for e in eventos if isinstance(e, Ferramenta)).chamadas
    assert len(chamadas) == 1
    assert chamadas[0].id == "call_1"
    assert chamadas[0].nome == "pesquisar_web"
    assert json.loads(chamadas[0].argumentos) == {"consulta": "dólar"}


async def test_reenvia_sem_ferramentas_se_provedor_rejeitar():
    corpos: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        corpo = json.loads(request.read())
        corpos.append(corpo)
        if "tools" in corpo:
            return httpx.Response(400, content=b"tools not supported")
        return httpx.Response(200, content=SSE)

    ferramenta = {"type": "function", "function": {"name": "x"}}
    cliente = ClienteOpenAICompat(
        _config(), transporte=httpx.MockTransport(handler)
    )
    eventos = [
        evento
        async for evento in cliente.stream(
            [{"role": "user", "content": "oi"}],
            temperatura=0.5,
            max_tokens=8,
            ferramentas=[ferramenta],
        )
    ]

    assert "tools" in corpos[0]
    assert "tools" not in corpos[1]
    assert [e.texto for e in eventos if isinstance(e, Delta)] == ["Olá", "!"]


async def test_envia_tool_choice_quando_pedido():
    corpos: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        corpos.append(json.loads(request.read()))
        return httpx.Response(
            200, content=SSE, headers={"content-type": "text/event-stream"}
        )

    ferramenta = {"type": "function", "function": {"name": "jw"}}
    cliente = ClienteOpenAICompat(
        _config(), transporte=httpx.MockTransport(handler)
    )
    async for _ in cliente.stream(
        [{"role": "user", "content": "oi"}],
        temperatura=0.5,
        max_tokens=8,
        ferramentas=[ferramenta],
        escolha_ferramenta="none",
    ):
        pass

    assert corpos[0]["tools"] == [ferramenta]
    assert corpos[0]["tool_choice"] == "none"


class _ClienteRoteiro:
    def __init__(self, eventos=(), erro: Exception | None = None) -> None:
        self.eventos = list(eventos)
        self.erro = erro
        self.chamadas = 0
        self.fechado = False

    async def stream(
        self,
        mensagens,
        *,
        temperatura,
        max_tokens,
        ferramentas=None,
        escolha_ferramenta=None,
    ):
        self.chamadas += 1
        for evento in self.eventos:
            yield evento
        if self.erro is not None:
            raise self.erro

    async def fechar(self) -> None:
        self.fechado = True


async def _coletar_roteiro(cliente):
    return [
        evento
        async for evento in cliente.stream(
            [{"role": "user", "content": "oi"}],
            temperatura=0.5,
            max_tokens=8,
        )
    ]


async def test_fallback_assume_quando_principal_falha_antes_do_token():
    primario = _ClienteRoteiro(erro=ErroDoProvedor("fora do ar", status=503))
    reserva = _ClienteRoteiro(eventos=[Delta("reserva"), Fim()])
    cliente = ClienteComFallback(primario, reserva)

    eventos = await _coletar_roteiro(cliente)

    assert [e.texto for e in eventos if isinstance(e, Delta)] == ["reserva"]
    assert primario.chamadas == 1
    assert reserva.chamadas == 1


async def test_fallback_nao_duplica_texto_se_principal_ja_emitiu():
    primario = _ClienteRoteiro(
        eventos=[Delta("parcial")],
        erro=ErroDoProvedor("caiu no meio"),
    )
    reserva = _ClienteRoteiro(eventos=[Delta("reserva"), Fim()])
    cliente = ClienteComFallback(primario, reserva)

    with pytest.raises(ErroDoProvedor):
        await _coletar_roteiro(cliente)

    assert reserva.chamadas == 0


async def test_fallback_nao_e_usado_quando_principal_termina():
    primario = _ClienteRoteiro(eventos=[Delta("ok"), Fim()])
    reserva = _ClienteRoteiro(eventos=[Delta("reserva"), Fim()])
    cliente = ClienteComFallback(primario, reserva)

    eventos = await _coletar_roteiro(cliente)

    assert [e.texto for e in eventos if isinstance(e, Delta)] == ["ok"]
    assert reserva.chamadas == 0


async def test_fallback_fecha_os_dois_clientes():
    primario = _ClienteRoteiro()
    reserva = _ClienteRoteiro()
    cliente = ClienteComFallback(primario, reserva)

    await cliente.fechar()

    assert primario.fechado is True
    assert reserva.fechado is True


def test_fallback_exige_base_e_modelo():
    with pytest.raises(ValueError, match="LLM_FALLBACK_BASE_URL"):
        Config(llm_fallback_model="minimax")


def test_url_chat_do_fallback():
    config = Config(
        llm_fallback_base_url="https://host/v1beta/openai/",
        llm_fallback_model="gemini-flash-latest",
    )
    assert config.fallback_ativa is True
    assert (
        config.url_chat_fallback
        == "https://host/v1beta/openai/chat/completions"
    )


def test_timeouts_do_principal_e_do_fallback_vem_do_env():
    config = Config.de_env(
        {
            "SERA_DEV": "1",
            "LLM_CONNECT_TIMEOUT": "5",
            "LLM_READ_TIMEOUT": "15",
            "LLM_FALLBACK_BASE_URL": "https://host/v1beta/openai",
            "LLM_FALLBACK_MODEL": "minimax",
            "LLM_FALLBACK_READ_TIMEOUT": "90",
        }
    )

    assert config.connect_timeout == 5
    assert config.read_timeout == 15
    assert config.llm_fallback_read_timeout == 90


def test_timeout_do_fallback_precisa_ser_positivo():
    with pytest.raises(ValueError, match="llm_fallback_read_timeout"):
        Config(
            llm_fallback_base_url="https://host/v1",
            llm_fallback_model="minimax",
            llm_fallback_read_timeout=0,
        )
