from datetime import datetime
from zoneinfo import ZoneInfo

from sera.api.relogio import bloco_agora, normalizar_consulta

MOMENTO = datetime(2026, 11, 1, 10, 32, tzinfo=ZoneInfo("America/Sao_Paulo"))


def test_bloco_agora_tem_data_e_referencias():
    bloco = bloco_agora(MOMENTO, "America/Sao_Paulo")

    assert "domingo, 01/11/2026, 10:32 (America/Sao_Paulo)" in bloco
    assert '"hoje" = 01/11/2026' in bloco
    assert '"ontem" = 31/10/2026' in bloco
    assert '"amanhã" = 02/11/2026' in bloco
    assert "26/10/2026 a 01/11/2026" in bloco
    assert "19/10/2026 a 25/10/2026" in bloco
    assert "novembro de 2026" in bloco
    assert "outubro de 2026" in bloco


def test_normalizar_consulta_substitui_datas_relativas():
    assert (
        normalizar_consulta("previsão do tempo hoje", MOMENTO)
        == "previsão do tempo 01/11/2026"
    )
    assert "31/10/2026" in normalizar_consulta("notícias de ontem", MOMENTO)
    assert "30/10/2026" in normalizar_consulta("o que houve anteontem", MOMENTO)
    assert "02/11/2026" in normalizar_consulta("agenda de amanhã", MOMENTO)
    assert "26/10/2026 a 01/11/2026" in normalizar_consulta(
        "o que bombou na última semana", MOMENTO
    )
    assert "19/10/2026 a 25/10/2026" in normalizar_consulta(
        "notícias da semana passada", MOMENTO
    )
    assert "novembro de 2026" in normalizar_consulta(
        "lançamentos deste mês", MOMENTO
    )
    assert "outubro de 2026" in normalizar_consulta(
        "resumo do mês passado", MOMENTO
    )


def test_hoje_em_dia_vira_atualmente():
    assert normalizar_consulta("hoje em dia", MOMENTO) == "atualmente"


def test_normalizar_consulta_preserva_texto_sem_data():
    assert normalizar_consulta("cotação do euro", MOMENTO) == "cotação do euro"