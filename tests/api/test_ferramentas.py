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


def test_formatar_resultado_jw_vira_texto_limpo():
    import json

    from sera.api.ferramentas import formatar_resultado_jw

    texto = json.dumps(
        {
            "reference": "Matthew 6:34-35",
            "verses": [
                {"verse_num": 34, "verse_text": "Nunca fiquem ansiosos."}
            ],
            "study_notes": {"34": "Nota sobre o amanhã."},
            "study_articles": [
                {
                    "title": "Como lidar com o estresse",
                    "url": "https://wol.jw.org/en/wol/pc/r1/lp-e/1/0",
                }
            ],
        },
        ensure_ascii=False,
    )

    saida = formatar_resultado_jw("get_verse_with_study", texto)

    assert "Referência: Matthew 6:34-35" in saida
    assert "34. Nunca fiquem ansiosos." in saida
    assert "Nota sobre o amanhã." in saida
    assert "Como lidar com o estresse" in saida
    assert "https://wol.jw.org" not in saida
    assert '"verse_num"' not in saida


def test_fontes_jw_usa_uma_fonte_principal():
    from sera.api.ferramentas import fontes_jw

    assert fontes_jw(
        "get_verse_with_study",
        {"book": 40, "chapter": 6, "verse": "34-35"},
        "{}",
    ) == [
        {
            "titulo": "Bíblia (jw.org)",
            "url": (
                "https://www.jw.org/finder?wtlocale=T&prefer=lang"
                "&bible=40006034-40006035&pub=nwtsty"
            ),
        }
    ]
    assert fontes_jw("get_bible_verse", {"book": 60, "chapter": 5, "verse": 7}, "{}") == [
        {
            "titulo": "Bíblia (jw.org)",
            "url": (
                "https://www.jw.org/finder?wtlocale=T&prefer=lang"
                "&bible=60005007&pub=nwtsty"
            ),
        }
    ]
    assert fontes_jw("search_bible_books", {"query": "mateus"}, "{}") == []
    assert fontes_jw("getWorkbookLinks", {}, "{}") == []
    assert fontes_jw(
        "getWorkbookContent", {"url": "https://cfp2.jw-cdn.org/a/x.rtf"}, "{}"
    ) == [{"titulo": "Apostila (CLM)", "url": "https://cfp2.jw-cdn.org/a/x.rtf"}]


def test_referencia_biblica():
    from sera.api.ferramentas import referencia_biblica

    assert referencia_biblica("o que diz 1 Pedro 5:7?") == (60, 5, 7, None)
    assert referencia_biblica("Salmo 23:1-3") == (19, 23, 1, 3)
    assert referencia_biblica("leia João 3:16") == (43, 3, 16, None)
    assert referencia_biblica("Mt 6:34") == (40, 6, 34, None)
    assert referencia_biblica("não é uma referência") is None
