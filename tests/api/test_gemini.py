from types import SimpleNamespace

import pytest
from google.genai import errors as gemini_errors
from google.genai import interactions as I

from sera.api.config import Config
from sera.api.llm import (
    ClienteGemini,
    Delta,
    ErroDoProvedor,
    Fim,
)

pytestmark = pytest.mark.anyio


def ns(**campos):
    return SimpleNamespace(**campos)


class _Fluxo:
    def __init__(self, eventos):
        self.eventos = list(eventos)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.eventos:
            raise StopAsyncIteration
        return self.eventos.pop(0)


class _Interacoes:
    def __init__(self, eventos=(), *, erro=None, erros=()):
        self.eventos = list(eventos)
        self.erro = erro
        self.erros = list(erros)
        self.chamadas = 0
        self.ultima = None

    async def create(self, **kwargs):
        self.chamadas += 1
        self.ultima = kwargs
        if self.erros:
            raise self.erros.pop(0)
        if self.erro is not None:
            raise self.erro
        return _Fluxo(self.eventos)


class _ClienteFake:
    def __init__(self, interacoes):
        self.aio = ns(interactions=interacoes)


def _config() -> Config:
    return Config(
        gemini_api_key="chave-fake",
        llm_model="gemini-3.8-flash",
    )


def _mensagens():
    return [
        {"role": "system", "content": "SYSTEM"},
        {"role": "user", "content": "oi"},
        {"role": "assistant", "content": "olá"},
        {"role": "user", "content": "de novo"},
    ]


async def _coletar(cliente):
    return [
        evento
        async for evento in cliente.stream(
            _mensagens(), temperatura=0.5, max_tokens=32
        )
    ]


async def test_converte_historico_e_streama():
    interacoes = _Interacoes(
        [
            ns(event_type="step.delta", delta=ns(type="text", text="Olá")),
            ns(event_type="step.delta", delta=ns(type="text", text="!")),
            ns(
                event_type="interaction.completed",
                interaction=ns(
                    usage=ns(
                        total_input_tokens=3,
                        total_output_tokens=2,
                        total_tokens=5,
                    ),
                    output_text="Olá!",
                ),
            ),
        ]
    )
    cliente = ClienteGemini(_config(), cliente=_ClienteFake(interacoes))

    eventos = await _coletar(cliente)

    assert [e.texto for e in eventos if isinstance(e, Delta)] == ["Olá", "!"]
    fim = eventos[-1]
    assert isinstance(fim, Fim)
    assert fim.uso is not None
    assert fim.uso.prompt_tokens == 3
    assert fim.uso.completion_tokens == 2
    assert fim.uso.total_tokens == 5

    chamada = interacoes.ultima
    assert chamada["model"] == "gemini-3.8-flash"
    assert chamada["stream"] is True
    assert chamada["store"] is False
    assert chamada["system_instruction"] == "SYSTEM"
    assert chamada["generation_config"] == {
        "temperature": 0.5,
        "max_output_tokens": 32,
    }
    assert chamada["input"] == [
        {
            "type": "user_input",
            "content": [{"type": "text", "text": "oi"}],
        },
        {
            "type": "model_output",
            "content": [{"type": "text", "text": "olá"}],
        },
        {
            "type": "user_input",
            "content": [{"type": "text", "text": "de novo"}],
        },
    ]


async def test_usa_output_text_quando_nao_ha_deltas():
    interacoes = _Interacoes(
        [
            ns(
                event_type="interaction.completed",
                interaction=ns(
                    usage=ns(
                        total_input_tokens=1,
                        total_output_tokens=4,
                        total_tokens=5,
                    ),
                    output_text="resposta inteira",
                ),
            )
        ]
    )
    cliente = ClienteGemini(_config(), cliente=_ClienteFake(interacoes))

    eventos = await _coletar(cliente)

    assert [e.texto for e in eventos if isinstance(e, Delta)] == [
        "resposta inteira"
    ]
    assert isinstance(eventos[-1], Fim)


async def test_evento_de_erro_vira_erro_do_provedor():
    interacoes = _Interacoes(
        [
            ns(
                event_type="error",
                error=ns(code=400, message="pedido inválido"),
            )
        ]
    )
    cliente = ClienteGemini(_config(), cliente=_ClienteFake(interacoes))

    with pytest.raises(ErroDoProvedor, match="pedido inválido"):
        await _coletar(cliente)


async def test_traduz_e_retenta_429_antes_do_primeiro_token():
    erro = gemini_errors.ClientError(
        429, {"error": {"message": "rate limit"}}
    )
    interacoes = _Interacoes(
        [ns(event_type="step.delta", delta=ns(type="text", text="ok"))],
        erros=[erro],
    )
    cliente = ClienteGemini(_config(), cliente=_ClienteFake(interacoes))

    eventos = await _coletar(cliente)

    assert interacoes.chamadas == 2
    assert [e.texto for e in eventos if isinstance(e, Delta)] == ["ok"]


async def test_erro_400_nao_retenta():
    erro = gemini_errors.ClientError(
        400, {"error": {"message": "modelo inválido"}}
    )
    interacoes = _Interacoes(erro=erro)
    cliente = ClienteGemini(_config(), cliente=_ClienteFake(interacoes))

    with pytest.raises(ErroDoProvedor) as capturado:
        await _coletar(cliente)

    assert interacoes.chamadas == 1
    assert capturado.value.status == 400
    assert capturado.value.retentavel is False


async def test_le_eventos_reais_do_sdk():
    eventos = [
        I.StepDelta(
            delta=I.TextDelta(type="text", text="oi"),
            index=0,
            event_type="step.delta",
        ),
        I.InteractionCompletedEvent(
            event_type="interaction.completed",
            interaction=I.InteractionSseEventInteraction(
                id="interacao-1",
                status="completed",
                usage=I.Usage(
                    total_input_tokens=1,
                    total_output_tokens=1,
                    total_tokens=2,
                ),
                steps=[
                    I.ModelOutputStep(
                        type="model_output",
                        content=[I.TextContent(type="text", text="oi")],
                    )
                ],
            ),
        ),
    ]
    interacoes = _Interacoes(eventos)
    cliente = ClienteGemini(_config(), cliente=_ClienteFake(interacoes))

    saida = await _coletar(cliente)

    assert [e.texto for e in saida if isinstance(e, Delta)] == ["oi"]
    assert saida[-1].uso.total_tokens == 2


def test_exige_chave_do_gemini():
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        ClienteGemini(Config())
