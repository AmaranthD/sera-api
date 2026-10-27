from pathlib import Path

import pytest

from sera.prompt import Camada

from . import cenarios

GOLDEN = Path(__file__).parent / "golden"

CENARIOS = {
    "adulto_padrao": cenarios.adulto_padrao,
    "adulto_ajustes_e_memoria": cenarios.adulto_ajustes_e_memoria,
    "crianca": cenarios.crianca,
    "idoso": cenarios.idoso,
}


@pytest.mark.parametrize("nome", sorted(CENARIOS))
def test_prompt_bate_com_o_golden(personality, nome):
    esperado = (GOLDEN / f"{nome}.txt").read_text(encoding="utf-8")
    assert CENARIOS[nome](personality).render() + "\n" == esperado


def test_base_tem_todas_as_secoes_curadas(personality):
    texto = cenarios.adulto_padrao(personality).render()
    for titulo in (
        "## Identidade",
        "## Tom",
        "## Humor",
        "## Toque dramático (teatral)",
        "## Como explica",
        "## Como ajuda",
        "## Situações específicas",
        "## Memória e uso do contexto",
        "## Limites da camada aprendida",
        "## Estilo efetivo para esta pessoa",
    ):
        assert titulo in texto


def test_base_nao_despeja_metadados_nem_presets(personality):
    texto = cenarios.adulto_padrao(personality).render()
    assert "versao" not in texto
    assert "perfil_crianca_adolescente" not in texto
    assert "perfil_idoso_ou_pouco_tecnico" not in texto


def test_titulos_das_camadas(personality):
    resultado = cenarios.adulto_ajustes_e_memoria(personality)
    titulos = {bloco.camada: bloco.titulo for bloco in resultado.blocos}
    assert titulos[Camada.LIMITES] == "# LIMITES INVIOLÁVEIS"
    assert titulos[Camada.AJUSTES] == "# AJUSTES APRENDIDOS"
    assert titulos[Camada.MEMORIA] == "# SOBRE A PESSOA"
    assert titulos[Camada.REFORCO] == "# LEMBRETE FINAL"
