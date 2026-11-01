import pytest

from sera.api.busca import ResultadoBusca
from sera.api.ferramentas import (
    ContextoFerramentas,
    FerramentaInvalida,
    bloco_resultados,
    consulta_esquecimento,
    consulta_explicita,
    esquemas,
    executar_ferramenta,
    extrair_urls_jw,
    titulo_fonte_jw,
)

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    ("mensagem", "esperado"),
    [
        ("pesquise previsão do tempo em São Paulo", "previsão do tempo em São Paulo"),
        ("Pesquise na internet sobre o museu Amanhã", "o museu Amanhã"),
        ("Sera, busque pra mim o preço do dólar", "o preço do dólar"),
        ("pode procurar na internet sobre a notícia X?", "a notícia X"),
        ("quero que você pesquise a cotação do euro", "a cotação do euro"),
        ("busca o horário do filme", "o horário do filme"),
        ("consulte o clima de amanhã no Rio", "o clima de amanhã no Rio"),
        ("Oi, tudo bem?", None),
        ("Vou pesquisar depois", None),
        ("pesquise nas minhas notas", None),
        ("não pesquise isso agora", None),
        ("me ajuda com minhas anotações", None),
        ("pesquise", None),
        ("", None),
    ],
)
def test_consulta_explicita(mensagem, esperado):
    assert consulta_explicita(mensagem) == esperado


async def test_executar_ferramenta_pesquisa_web():
    chamadas: list[str] = []

    class BuscaFalsa:
        async def pesquisar(self, consulta: str):
            chamadas.append(consulta)
            return [
                ResultadoBusca(
                    titulo="Exemplo",
                    url="https://exemplo.com",
                    trecho="trecho",
                )
            ]

    resultado = await executar_ferramenta(
        "pesquisar_web",
        '{"consulta": "clima em Recife"}',
        ContextoFerramentas(busca=BuscaFalsa()),
    )

    assert chamadas == ["clima em Recife"]
    assert resultado["resultados"][0]["url"] == "https://exemplo.com"


async def test_executar_ferramenta_rejeita_json_invalido():
    with pytest.raises(FerramentaInvalida):
        await executar_ferramenta(
            "pesquisar_web", "{nao é json", ContextoFerramentas()
        )


def test_bloco_resultados_delimita_conteudo_nao_confiavel():
    bloco = bloco_resultados(
        "clima",
        [
            ResultadoBusca(
                titulo="Tempo",
                url="https://exemplo.com/tempo",
                trecho="Sol.",
            )
        ],
    )

    assert 'Consulta: "clima"' in bloco
    assert "https://exemplo.com/tempo" in bloco
    assert "<<<INÍCIO DOS RESULTADOS" in bloco
    assert "<<<FIM DOS RESULTADOS>>>" in bloco


@pytest.mark.parametrize(
    ("mensagem", "esperado"),
    [
        ("esqueça que eu gosto de jazz", "gosto de jazz"),
        ("esquece a memória sobre jazz", "jazz"),
        ("não lembre mais de jazz", "jazz"),
        ("esqueça o fato de que eu gosto de jazz", "gosto de jazz"),
        ("não esqueça de comprar leite", None),
        ("esqueça isso", None),
        ("Oi, tudo bem?", None),
        ("", None),
    ],
)
def test_consulta_esquecimento(mensagem, esperado):
    assert consulta_esquecimento(mensagem) == esperado


def test_extrair_urls_jw_so_aceita_dominios_jw():
    texto = (
        '{"articles": [{"url": "https://cfp2.jw-cdn.org/a/abc.rtf"}, '
        '{"url": "https://www.jw.org/finder?bible=19123001"}], '
        '"fonte": "https://exemplo.com/nao-vale"}'
    )
    assert extrair_urls_jw(texto) == [
        "https://cfp2.jw-cdn.org/a/abc.rtf",
        "https://www.jw.org/finder?bible=19123001",
    ]


def test_extrair_urls_jw_deduplica_e_limita():
    texto = " ".join(
        f"https://www.jw.org/pagina?n={indice}" for indice in range(12)
    )
    urls = extrair_urls_jw(texto)
    assert len(urls) == 8
    assert len(set(urls)) == 8
    assert extrair_urls_jw("https://www.jw.org/a).") == ["https://www.jw.org/a"]


def test_titulo_fonte_jw():
    assert titulo_fonte_jw("get_verse_with_study").startswith("JW · versículo")
    assert titulo_fonte_jw("desconhecida") == "JW"


def test_esquemas_modo_jw_inclui_jw_e_memoria():
    nomes = {
        item["function"]["name"]
        for item in esquemas(busca=False, aprendizado=True, jw=True)
    }
    assert nomes == {"jw", "lembrar", "ajustar_preferencia", "esquecer"}


def test_ferramentas_jw_para_filtra_por_assunto():
    from sera.api.ferramentas import ferramentas_jw_para

    biblia = {
        "search_bible_books",
        "get_bible_verse",
        "get_verse_with_study",
        "get_bible_verse_url",
    }
    assert set(ferramentas_jw_para("estou ansioso")) == biblia
    apostila = set(ferramentas_jw_para("quero a apostila desta semana"))
    assert {"getWorkbookLinks", "getWorkbookContent"} <= apostila
    sentinela = set(ferramentas_jw_para("o que a Sentinela diz sobre ansiedade?"))
    assert {"getWatchtowerLinks", "getWatchtowerContent"} <= sentinela
    assert "getWorkbookLinks" not in sentinela


def test_esquemas_filtra_enum_jw():
    from sera.api.ferramentas import ferramentas_jw_para

    (esquema,) = esquemas(
        jw=True,
        jw_ferramentas=ferramentas_jw_para("ansiedade"),
    )
    enum = esquema["function"]["parameters"]["properties"]["ferramenta"]["enum"]
    assert "get_bible_verse" in enum
    assert "getWorkbookLinks" not in enum
