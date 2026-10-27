from __future__ import annotations

import pytest

from sera.rag import (
    DIRETORIOS_IGNORADOS,
    expressao_fts,
    iterar_notas,
    ler_nota,
    termos_busca,
)


def escrever(caminho, texto):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto, encoding="utf-8")
    return caminho


def test_le_frontmatter_titulo_e_secoes(tmp_path):
    nota = ler_nota(
        escrever(
            tmp_path / "Projetos" / "Sera.md",
            "---\ntags:\n  - projeto\n  - ia\n---\n\n"
            "# Seraphine\n\nVoltar: [[IA]]\n\n"
            "## Visão\n\n- base de conhecimento\n\n"
            "## Fases\n\n- [ ] MVP\n",
        ),
        raiz=tmp_path,
    )

    assert nota.caminho == "Projetos/Sera.md"
    assert nota.titulo == "Seraphine"
    assert nota.tags == ("projeto", "ia")
    assert [secao.nome for secao in nota.secoes] == ["", "Visão", "Fases"]
    assert "Voltar" in nota.secoes[0].texto
    assert "MVP" in nota.secoes[2].texto


def test_titulo_cai_para_o_nome_do_arquivo(tmp_path):
    nota = ler_nota(escrever(tmp_path / "Sem Titulo.md", "só texto\n"))
    assert nota.titulo == "Sem Titulo"
    assert [secao.nome for secao in nota.secoes] == [""]


def test_frontmatter_invalido_nao_quebra(tmp_path):
    nota = ler_nota(escrever(tmp_path / "N.md", "---\ntags: [a\n---\n# N\n\ntexto"))
    assert nota.titulo == "N"
    assert nota.tags == ()


def test_hash_muda_quando_o_texto_muda(tmp_path):
    caminho = escrever(tmp_path / "N.md", "# N\n\nigual\n")
    primeiro = ler_nota(caminho)
    caminho.write_text("# N\n\nmudou\n", encoding="utf-8")
    assert ler_nota(caminho).hash != primeiro.hash
    assert ler_nota(caminho).hash == ler_nota(caminho).hash


def test_tags_aceitam_string_com_virgulas(tmp_path):
    nota = ler_nota(escrever(tmp_path / "N.md", "---\ntags: 'Projeto, #IA'\n---\n"))
    assert nota.tags == ("projeto", "ia")


def test_iterar_notas_ignora_pastas_de_ruido(tmp_path):
    escrever(tmp_path / "Boa.md", "# Boa\n\ntexto")
    escrever(tmp_path / "Templates" / "Modelo.md", "# Modelo\n\ntexto")
    escrever(tmp_path / ".obsidian" / "x.md", "# X\n\ntexto")
    escrever(tmp_path / "Sub" / ".trash" / "y.md", "# Y\n\ntexto")

    caminhos = [nota.caminho for nota in iterar_notas(tmp_path)]

    assert caminhos == ["Boa.md"]
    assert "Templates" in DIRETORIOS_IGNORADOS


def test_termos_busca_normaliza_e_deduplica():
    assert termos_busca("O Wi-Fi caiu, o wi-fi de novo!") == ["caiu", "novo"]
    assert termos_busca("") == []
    assert termos_busca("ab cd") == []


def test_expressao_fts_cita_cada_termo():
    assert expressao_fts("wifi caiu") == '"wifi" OR "caiu"'
    assert expressao_fts("!!!") == ""


def test_expressao_fts_nao_permite_sintaxe_arbitraria():
    expressao = expressao_fts('x" OR * NEAR(y)')
    assert '"x' not in expressao or '""' in expressao
    assert expressao.count('"') % 2 == 0


@pytest.mark.parametrize("texto", ["", "   "])
def test_nota_vazia_nao_gera_secoes(tmp_path, texto):
    nota = ler_nota(escrever(tmp_path / "V.md", texto))
    assert nota.secoes == ()
