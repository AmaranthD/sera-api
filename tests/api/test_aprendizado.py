import pytest

from sera.api.db import Banco
from sera.api.ferramentas import (
    ContextoFerramentas,
    FerramentaInvalida,
    executar_ferramenta,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
async def banco(tmp_path):
    base = Banco(tmp_path / "sera.db")
    base.iniciar()
    await base.criar_pessoa("maria", "Maria", "adulto", "padrao", True)
    return base


@pytest.fixture
def contexto(banco):
    return ContextoFerramentas(banco=banco, pessoa_id="maria")


async def test_lembrar_salva_fato(banco, contexto):
    resultado = await executar_ferramenta(
        "lembrar",
        '{"texto": "Gosta de jazz", "categoria": "gostos"}',
        contexto,
    )

    assert resultado["ok"] is True
    memorias = await banco.listar_memorias("maria")
    assert [item["texto"] for item in memorias] == ["Gosta de jazz"]
    assert memorias[0]["categoria"] == "gostos"


async def test_lembrar_nao_duplica(banco, contexto):
    await executar_ferramenta(
        "lembrar",
        '{"texto": "Gosta de jazz", "categoria": "gostos"}',
        contexto,
    )
    resultado = await executar_ferramenta(
        "lembrar",
        '{"texto": "gosta de JAZZ", "categoria": "gostos"}',
        contexto,
    )

    assert resultado["duplicada"] is True
    assert len(await banco.listar_memorias("maria")) == 1


async def test_lembrar_recusa_dado_sensivel(contexto):
    with pytest.raises(FerramentaInvalida, match="sensíveis"):
        await executar_ferramenta(
            "lembrar",
            '{"texto": "A senha do wi-fi é 1234", "categoria": "outro"}',
            contexto,
        )


async def test_lembrar_categoria_invalida_vira_outro(banco, contexto):
    await executar_ferramenta(
        "lembrar",
        '{"texto": "Tem um gato chamado Tom", "categoria": "bichos"}',
        contexto,
    )

    assert (await banco.listar_memorias("maria"))[0]["categoria"] == "outro"


async def test_ajustar_salva_apelido(banco, contexto):
    resultado = await executar_ferramenta(
        "ajustar_preferencia",
        '{"tipo": "apelido", "texto": "Mãe Sera"}',
        contexto,
    )

    assert resultado["ok"] is True
    ajustes = await banco.listar_ajustes("maria")
    assert [(item["tipo"], item["texto"]) for item in ajustes] == [
        ("apelido", "Mãe Sera")
    ]


async def test_ajustar_nivel_substitui_o_anterior(banco, contexto):
    await executar_ferramenta(
        "ajustar_preferencia",
        '{"tipo": "nivel_sarcasmo", "valor": "alto"}',
        contexto,
    )
    await executar_ferramenta(
        "ajustar_preferencia",
        '{"tipo": "nivel_sarcasmo", "valor": "leve"}',
        contexto,
    )

    ajustes = await banco.listar_ajustes("maria")
    assert len(ajustes) == 1
    assert ajustes[0]["valor"] == "leve"


async def test_ajustar_recusa_valor_invalido(contexto):
    with pytest.raises(FerramentaInvalida):
        await executar_ferramenta(
            "ajustar_preferencia",
            '{"tipo": "formalidade", "valor": "extrema"}',
            contexto,
        )


async def test_ajustar_respeita_limite(banco, contexto, monkeypatch):
    monkeypatch.setattr("sera.api.ferramentas._MAX_AJUSTES", 1)
    await executar_ferramenta(
        "ajustar_preferencia",
        '{"tipo": "apelido", "texto": "Mãe Sera"}',
        contexto,
    )

    with pytest.raises(FerramentaInvalida, match="20 ajustes"):
        await executar_ferramenta(
            "ajustar_preferencia",
            '{"tipo": "assunto", "texto": "jazz"}',
            contexto,
        )
