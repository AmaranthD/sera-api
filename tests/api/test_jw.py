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


async def test_cliente_jw_devolve_texto_completo():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_resposta("abcdefghij"))

    cliente = ClienteJW(
        _config(jw_max_chars=5), transporte=httpx.MockTransport(handler)
    )
    resposta = await cliente.executar("search_bible_books", {"query": "matthew"})

    # O corte é aplicado depois de formatar o JSON, em _jw.
    assert resposta.texto == "abcdefghij"


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
            "titulo": "Bíblia (jw.org)",
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


async def test_ultima_rodada_proibe_novas_ferramentas(config):
    fake = FakeLLM(chunks=["Resposta final."])
    jw = FakeJW("Mateus 6:34")
    fake.chamadas = [
        ChamadaFerramenta(
            id="call_1",
            nome="jw",
            argumentos='{"ferramenta": "get_bible_verse", "book": 40, '
            '"chapter": 6, "verse": "34"}',
        )
    ]
    app = criar_app(
        replace(
            config,
            jw_api_url="https://jw.test/api",
            jw_api_key="chave",
            jw_max_rodadas=1,
        ),
        llm=fake,
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
                "mensagem": "o que a Bíblia diz sobre perdão?",
                "fonte": "jw",
            },
        )

    assert resposta.status_code == 200
    assert fake.chamadas_recebidas == 2
    # A última rodada mantém os esquemas, mas com tool_choice="none".
    assert fake.ferramentas is not None
    assert fake.escolha_ferramenta == "none"
    assert "Não chame ferramentas" in system_prompt(fake)
    assert (
        "https://www.jw.org/finder?wtlocale=T&prefer=lang"
        "&bible=40006034&pub=nwtsty"
    ) in system_prompt(fake)


async def test_cliente_jw_aquece_e_reaproveita_o_cache():
    caminhos: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        caminhos.append(request.url.path)
        return httpx.Response(200, json={"status": "ok"})

    cliente = ClienteJW(_config(), transporte=httpx.MockTransport(handler))
    await cliente.aquecer()
    await cliente.aquecer()

    assert caminhos == ["/health"]


async def test_cliente_jw_repete_502_do_render():
    respostas = [httpx.Response(502, text="<html>subindo</html>")]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if respostas:
            return respostas.pop(0)
        return httpx.Response(200, json=_resposta())

    cliente = ClienteJW(_config(), transporte=httpx.MockTransport(handler))
    resposta = await cliente.executar("search_bible_books", {"query": "matthew"})

    assert resposta.texto == "Matthew (40)"


async def test_modo_jw_acorda_o_servico_antes_do_chat(config):
    fake = FakeLLM(chunks=["ok"])
    jw = FakeJW("Mateus")
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
        resposta = await cliente.post(
            "/chat",
            json={"pessoa_id": "maria", "mensagem": "oi", "fonte": "jw"},
        )

    assert resposta.status_code == 200
    assert jw.aquecimentos == 1


async def test_ferramenta_jw_normaliza_tipos_do_scraper():
    jw = FakeJW("1 Pedro 5:7")
    contexto = ContextoFerramentas(jw=jw)

    await executar_ferramenta(
        "jw",
        '{"ferramenta": "get_bible_verse", "book": "60", '
        '"chapter": "5", "verse": "7"}',
        contexto,
    )
    await executar_ferramenta(
        "jw",
        '{"ferramenta": "get_verse_with_study", "book": 40, '
        '"chapter": 6, "verse": "1,3,5"}',
        contexto,
    )

    assert jw.chamadas == [
        ("get_bible_verse", {"book": 60, "chapter": 5, "verse": 7}),
        ("get_verse_with_study", {"book": 40, "chapter": 6, "verse": "1-5"}),
    ]


async def test_modo_jw_emite_apenas_uma_fonte(config):
    fake = FakeLLM(chunks=["Pronto."])
    jw = FakeJW("https://www.jw.org/finder?bible=19023001")
    fake.chamadas = [
        ChamadaFerramenta(
            id="call_1",
            nome="jw",
            argumentos=(
                '{"ferramenta": "get_bible_verse_url", '
                '"book": 19, "chapter": 23, "verse": 1}'
            ),
        ),
        ChamadaFerramenta(
            id="call_2",
            nome="jw",
            argumentos=(
                '{"ferramenta": "get_bible_verse", '
                '"book": 40, "chapter": 6, "verse": 34}'
            ),
        ),
    ]
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
        resposta = await cliente.post(
            "/chat",
            json={
                "pessoa_id": "maria",
                "mensagem": "fale sobre esperança e ansiedade",
                "fonte": "jw",
            },
        )

    ev = eventos(resposta.text)
    fontes = [dados for nome, dados in ev if nome == "sources"]
    assert len(fontes) == 1
    assert len(fontes[0]["fontes"]) == 1
    assert fontes[0]["fontes"][0]["titulo"] == "Bíblia (jw.org)"


async def test_modo_jw_consulta_referencia_antes_do_modelo(config):
    versiculo = json.dumps(
        {
            "reference": "1 Peter 5:7",
            "verses": [
                {
                    "verse_num": 7,
                    "verse_text": "Lancem sobre ele toda a sua ansiedade.",
                }
            ],
            "study_notes": {"7": "Jeová se importa com você."},
            "study_articles": [
                {
                    "title": "Ansiedade",
                    "url": "https://wol.jw.org/en/wol/pc/r1/lp-e/1/0",
                }
            ],
        },
        ensure_ascii=False,
    )
    fake = FakeLLM(chunks=["Pronto."])
    jw = FakeJW(versiculo)
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
        resposta = await cliente.post(
            "/chat",
            json={
                "pessoa_id": "maria",
                "mensagem": "o que diz 1 Pedro 5:7?",
                "fonte": "jw",
            },
        )

    assert resposta.status_code == 200
    assert jw.chamadas == [
        (
            "get_verse_with_study",
            {
                "book": 60,
                "chapter": 5,
                "verse": "7",
                "fields": ["verses", "study_notes"],
            },
        )
    ]
    # O texto já veio pronto: o modelo não precisa chamar ferramenta.
    assert fake.chamadas_recebidas == 1
    prompt = system_prompt(fake)
    assert "Lancem sobre ele toda a sua ansiedade." in prompt
    assert "Jeová se importa com você." in prompt
    assert "https://wol.jw.org" not in prompt
    assert "## Fontes" in prompt

    nomes = {item["function"]["name"] for item in (fake.ferramentas or [])}
    assert "jw" not in nomes

    fontes = [dados for nome, dados in eventos(resposta.text) if nome == "sources"]
    assert len(fontes) == 1
    assert len(fontes[0]["fontes"]) == 1
    assert fontes[0]["fontes"][0]["url"].endswith(
        "bible=60005007&pub=nwtsty"
    )
