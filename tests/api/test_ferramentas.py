import pytest

from sera.api.busca import ResultadoBusca
from sera.api.ferramentas import (
    ContextoFerramentas,
    FerramentaInvalida,
    bloco_resultados,
    consulta_esquecimento,
    consulta_explicita,
    executar_ferramenta,
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
