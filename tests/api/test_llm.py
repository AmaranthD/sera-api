import json

import httpx
import pytest

from sera.api.config import Config
from sera.api.llm import (
    ClienteOpenAICompat,
    Delta,
    ErroDoProvedor,
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
