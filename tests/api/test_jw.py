import json
from dataclasses import replace

import httpx
import pytest

from sera.api import Config, criar_app
from sera.api.ferramentas import ContextoFerramentas, executar_ferramenta
from sera.api.jw import ClienteJW, JWIndisponivel
from sera.api.llm import ChamadaFerramenta
from tests.api.ajuda import (
    FakeBusca,
    FakeJW,
    FakeLLM,
    criar_pessoa,
    eventos,
    system_prompt,
    tokens,
)

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


async def test_modo_jw_desliga_busca_e_emite_fontes(config):
    fake = FakeLLM(
        chunks=[
            "O Senhor é meu pastor.\n\n## Fontes\n"
            "- https://www.jw.org/finder?bible=19123001"
        ]
    )
    jw = FakeJW(
        "https://www.jw.org/finder?wtlocale=E&bible=19123001&pub=nwtsty"
    )
    busca = FakeBusca(
        [
            {
                "titulo": "Resultado web",
                "url": "https://exemplo.com/fora",
                "trecho": "não deveria aparecer",
            }
        ]
    )
    fake.chamadas = [
        ChamadaFerramenta(
            id="call_1",
            nome="jw",
            argumentos=(
                '{"ferramenta": "get_bible_verse_url", '
                '"argumentos": {"book": 19, "chapter": 23, "verse": 1}}'
            ),
        )
    ]
    app = criar_app(
        replace(
            config,
            busca_habilitada=True,
            tavily_api_key="tvly-teste",
            jw_api_url="https://jw.test/api",
            jw_api_key="chave",
        ),
        llm=fake,
        busca=busca,
        jw=jw,
    )
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        await criar_pessoa(cliente)
        resposta = await cliente.post(
            "/chat",
            json={
                "pessoa_id": "maria",
                "mensagem": "pesquise sobre o Salmo 23",
                "fonte": "jw",
            },
        )

    assert resposta.status_code == 200
    # Mesmo com "pesquise", a internet não é consultada.
    assert busca.consultas == []
    assert jw.chamadas == [
        ("get_bible_verse_url", {"book": 19, "chapter": 23, "verse": 1})
    ]

    nomes = {item["function"]["name"] for item in (fake.ferramentas or [])}
    assert "pesquisar_web" not in nomes
    assert "jw" in nomes

    prompt = system_prompt(fake)
    assert "Modo JW (fonte única)" in prompt
    assert "Busca na internet" not in prompt

    ev = eventos(resposta.text)
    fontes = [dados for nome, dados in ev if nome == "sources"]
    assert fontes[0]["fontes"] == [
        {
            "titulo": "JW · Bíblia",
            "url": "https://www.jw.org/finder?wtlocale=E&bible=19123001&pub=nwtsty",
        }
    ]
    assert tokens(ev) == [
        "O Senhor é meu pastor.\n\n## Fontes\n"
        "- https://www.jw.org/finder?bible=19123001"
    ]


async def test_modo_jw_sem_servico_responde_503(cliente):
    await criar_pessoa(cliente)
    resposta = await cliente.post(
        "/chat",
        json={"pessoa_id": "maria", "mensagem": "oi", "fonte": "jw"},
    )
    assert resposta.status_code == 503


async def test_ferramenta_jw_aceita_argumentos_achatados():
    jw = FakeJW("Salmo 23")
    contexto = ContextoFerramentas(jw=jw)

    resultado = await executar_ferramenta(
        "jw",
        '{"ferramenta": "get_verse_with_study", "book": 19, '
        '"chapter": 23, "verse": "1-3"}',
        contexto,
    )

    assert resultado["texto"] == "Salmo 23"
    assert jw.chamadas == [
        ("get_verse_with_study", {"book": 19, "chapter": 23, "verse": "1-3"})
    ]


async def test_ferramenta_jw_recusa_nome_desconhecido():
    with pytest.raises(Exception, match="desconhecida"):
        await executar_ferramenta(
            "jw", '{"ferramenta": "inventada"}', ContextoFerramentas(jw=FakeJW())
        )
