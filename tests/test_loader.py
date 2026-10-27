from pathlib import Path

import pytest
import yaml

from sera.prompt import PersonalityInvalida, carregar_personality

RAIZ = Path(__file__).resolve().parents[1]


def _bruto():
    return yaml.safe_load((RAIZ / "personality.yaml").read_text(encoding="utf-8"))


def _escrever(tmp_path, dados):
    caminho = tmp_path / "personality.yaml"
    caminho.write_text(
        yaml.safe_dump(dados, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return caminho


def test_carrega_o_yaml_real(personality):
    assert personality.versao == 1
    assert personality.identidade["nome"] == "Seraphine"
    assert "seguranca_pessoal" in personality.limites_inviolaveis
    assert personality.limites_inviolaveis["honestidade"][0].startswith(
        "Nunca fingir ser humana"
    )


def test_limites_do_yaml_real_continuam_textuais(personality):
    for itens in personality.limites_inviolaveis.values():
        assert all(isinstance(item, str) for item in itens)


def test_recusa_versao_desconhecida(tmp_path):
    dados = _bruto()
    dados["versao"] = 2
    with pytest.raises(PersonalityInvalida, match="versão"):
        carregar_personality(_escrever(tmp_path, dados))


def test_recusa_limites_ausentes(tmp_path):
    dados = _bruto()
    dados["limites_inviolaveis"] = {}
    with pytest.raises(PersonalityInvalida, match="limites_inviolaveis"):
        carregar_personality(_escrever(tmp_path, dados))


def test_recusa_categoria_de_limite_vazia(tmp_path):
    dados = _bruto()
    dados["limites_inviolaveis"]["honestidade"] = []
    with pytest.raises(PersonalityInvalida, match="honestidade"):
        carregar_personality(_escrever(tmp_path, dados))


def test_recusa_secao_ausente(tmp_path):
    dados = _bruto()
    del dados["tom"]
    with pytest.raises(PersonalityInvalida, match="tom"):
        carregar_personality(_escrever(tmp_path, dados))


def test_recusa_knob_invalido_no_padrao(tmp_path):
    dados = _bruto()
    dados["adaptacao_por_usuario"]["padrao"]["nivel_sarcasmo"] = "extremo"
    with pytest.raises(PersonalityInvalida, match="nivel_sarcasmo"):
        carregar_personality(_escrever(tmp_path, dados))


def test_recusa_knob_invalido_em_preset(tmp_path):
    dados = _bruto()
    dados["adaptacao_por_usuario"]["perfil_crianca_adolescente"]["toque_yandere"] = (
        "medio"
    )
    dados["adaptacao_por_usuario"]["perfil_crianca_adolescente"]["formalidade"] = (
        "altissima"
    )
    with pytest.raises(PersonalityInvalida, match="formalidade"):
        carregar_personality(_escrever(tmp_path, dados))


def test_recusa_yaml_malformado(tmp_path):
    caminho = tmp_path / "personality.yaml"
    caminho.write_text("limites: [aberto", encoding="utf-8")
    with pytest.raises(PersonalityInvalida, match="YAML"):
        carregar_personality(caminho)


def test_recusa_arquivo_inexistente(tmp_path):
    with pytest.raises(PersonalityInvalida, match="não encontrado"):
        carregar_personality(tmp_path / "nao-existe.yaml")
