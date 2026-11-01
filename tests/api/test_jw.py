import json
from dataclasses import replace

import httpx
import pytest

from sera.api import Config, criar_app
from sera.api.ferramentas import ContextoFerramentas, executar_ferramenta
from sera.api.jw import ClienteJW, JWIndisponivel
from sera.api.llm import ChamadaFerramenta
from tests.api.ajuda import FakeJW, FakeLLM, criar_pessoa, eventos, system_prompt, tokens

pytestmark = pytest.mark.anyio


def _config(**kwargs) -> Config:
    base = {
        "jw_api_url": "https://jw.test/api",
        "jw_api_key": "chave-jw",
    }
    base.update(kwargs)
    return Config(**base)


def _resposta(texto: str = "Matthew (40)") -> dict:
    return {
        "ferramenta": "search_bible_books",
        "resultado": {"content": [{"type": "text", "text": texto}]},
    }


async def test_cliente_jw_chama_facade_com_api_key():
    pedidos: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        pedidos.append(request)
        return httpx.Response(200, json=_resposta())

    cliente = ClienteJW(_config(), transporte=httpx.MockTransport(handler))
    resposta = await cliente.executar("search_bible_books", {"query": "matthew"})

    assert resposta.texto == "Matthew (40)"
    assert resposta.erro is False
    requisicao = pedidos[0]
    assert str(requisicao.url) == "https://jw.test/api/tool"
    assert requisicao.headers["x-api-key"] == "chave-jw"
    assert json.loads(requisicao.read()) == {
        "nome": "search_bible_books",
        "argumentos": {"query": "matthew"},
    }


async def test_cliente_jw_401_vira_indisponivel():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"erro": "API key inválida"})

    cliente = ClienteJW(_config(), transporte=httpx.MockTransport(handler))
    with pytest.raises(JWIndisponivel) as capturado:
        await cliente.executar("search_bible_books", {"query": "matthew"})
    assert capturado.value.status == 401


async def test_cliente_jw_timeout_vira_indisponivel():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("demorou", request=request)

    cliente = ClienteJW(_config(), transporte=httpx.MockTransport(handler))
    with pytest.raises(JWIndisponivel, match="timeout"):
        await cliente.executar("search_bible_books", {"query": "matthew"})


async def test_cliente_jw_limita_tamanho():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_resposta("abcdefghij"))

    cliente = ClienteJW(
        _config(jw_max_chars=5), transporte=httpx.MockTransport(handler)
    )
    resposta = await cliente.executar("search_bible_books", {"query": "matthew"})

    assert resposta.texto == "abcde…"


async def test_ferramenta_jw_delega_ao_cliente():
    jw = FakeJW("Mateus 5:3-5")
    contexto = ContextoFerramentas(jw=jw)

    resultado = await executar_ferramenta(
        "jw",
        '{"ferramenta": "get_verse_with_study", "argumentos": {"book": 40}}',
        contexto,
    )

    assert resultado["texto"] == "Mateus 5:3-5"
    assert jw.chamadas == [("get_verse_with_study", {"book": 40})]


async def test_chat_usa_ferramenta_jw(config):
    fake = FakeLLM()
    jw = FakeJW("Mateus é o livro 40.")
    app = criar_app(
        replace(config, jw_api_url="https://jw.test/api", jw_api_key="chave"),
        llm=fake,
        jw=jw,
    )
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        await criar_pessoa(cliente)
        fake.chamadas = [
            ChamadaFerramenta(
                id="call_1",
                nome="jw",
                argumentos=(
                    '{"ferramenta": "search_bible_books", '
                    '"argumentos": {"query": "matthew"}}'
                ),
            )
        ]
        fake.chunks = ["Mateus é o livro 40."]
        resposta = await cliente.post(
            "/chat",
            json={"pessoa_id": "maria", "mensagem": "qual o livro de Mateus?"},
        )

    assert fake.chamadas_recebidas == 2
    assert jw.chamadas == [("search_bible_books", {"query": "matthew"})]
    assert "## Conteúdo JW" in system_prompt(fake)
    assert "Mateus é o livro 40." in system_prompt(fake)
    assert tokens(eventos(resposta.text)) == ["Mateus é o livro 40."]
