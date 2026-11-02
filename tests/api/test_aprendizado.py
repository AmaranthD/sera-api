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
    monkeypatch.setattr("sera.api.ferramentas_memoria._MAX_AJUSTES", 1)
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


async def test_lembrar_saude_exige_confirmacao(banco, contexto):
    sem_confirmar = await executar_ferramenta(
        "lembrar",
        '{"texto": "Tem diabetes", "categoria": "saude"}',
        contexto,
    )
    assert sem_confirmar["precisa_confirmar"] is True
    assert await banco.listar_memorias("maria") == []

    # O modelo pode mandar confirmado=true, mas sem o sim da pessoa não grava.
    forcado = await executar_ferramenta(
        "lembrar",
        '{"texto": "Tem diabetes", "categoria": "saude", "confirmado": true}',
        contexto,
    )
    assert forcado["precisa_confirmar"] is True
    assert await banco.listar_memorias("maria") == []

    autorizado = ContextoFerramentas(
        banco=banco,
        pessoa_id="maria",
        mensagem_usuario="sim, pode guardar",
    )
    confirmado = await executar_ferramenta(
        "lembrar",
        '{"texto": "Tem diabetes", "categoria": "saude", "confirmado": true}',
        autorizado,
    )
    assert confirmado["ok"] is True
    assert [m["texto"] for m in await banco.listar_memorias("maria")] == [
        "Tem diabetes"
    ]


async def test_lembrar_saude_aceita_pedido_explicito(banco):
    contexto = ContextoFerramentas(
        banco=banco,
        pessoa_id="maria",
        mensagem_usuario="lembre que eu tenho diabetes",
    )
    resultado = await executar_ferramenta(
        "lembrar",
        '{"texto": "Tem diabetes", "categoria": "saude", "confirmado": true}',
        contexto,
    )

    assert resultado["ok"] is True
    assert [m["texto"] for m in await banco.listar_memorias("maria")] == [
        "Tem diabetes"
    ]


async def test_lembrar_respeita_limite(banco, contexto, monkeypatch):
    monkeypatch.setattr("sera.api.ferramentas_memoria._MAX_MEMORIAS", 1)
    await executar_ferramenta(
        "lembrar",
        '{"texto": "Gosta de jazz", "categoria": "gostos"}',
        contexto,
    )

    with pytest.raises(FerramentaInvalida, match="100 memórias"):
        await executar_ferramenta(
            "lembrar",
            '{"texto": "Gosta de rock", "categoria": "gostos"}',
            contexto,
        )


async def test_esquecer_pede_confirmacao(banco, contexto):
    await executar_ferramenta(
        "lembrar",
        '{"texto": "Gosta de jazz", "categoria": "gostos"}',
        contexto,
    )

    sem_confirmar = await executar_ferramenta(
        "esquecer", '{"texto": "jazz"}', contexto
    )
    assert sem_confirmar["precisa_confirmar"] is True
    assert len(await banco.listar_memorias("maria")) == 1

    confirmado = await executar_ferramenta(
        "esquecer", '{"texto": "jazz", "confirmado": true}', contexto
    )
    assert confirmado["ok"] is True
    assert await banco.listar_memorias("maria") == []


async def test_esquecer_ambigua_devolve_candidatas(banco, contexto):
    for texto in ("Gosta de jazz", "Gosta de jazz e blues"):
        await executar_ferramenta(
            "lembrar",
            f'{{"texto": "{texto}", "categoria": "gostos"}}',
            contexto,
        )

    resultado = await executar_ferramenta(
        "esquecer", '{"texto": "jazz", "confirmado": true}', contexto
    )

    assert resultado["ambigua"] is True
    assert len(resultado["candidatas"]) == 2
    assert len(await banco.listar_memorias("maria")) == 2


async def test_esquecer_sem_correspondencia(contexto):
    resultado = await executar_ferramenta(
        "esquecer", '{"texto": "praia", "confirmado": true}', contexto
    )

    assert resultado["encontrada"] is False


async def test_esquecer_aceita_flexao_verbal(banco, contexto):
    await executar_ferramenta(
        "lembrar",
        '{"texto": "Gosta de jazz.", "categoria": "gostos"}',
        contexto,
    )

    resultado = await executar_ferramenta(
        "esquecer", '{"texto": "gosto de jazz", "confirmado": true}', contexto
    )

    assert resultado["ok"] is True
    assert await banco.listar_memorias("maria") == []


async def test_esquecer_prefere_correspondencia_exata(banco, contexto):
    for texto in ("Gosta de jazz", "Gosta de jazz e blues"):
        await executar_ferramenta(
            "lembrar",
            f'{{"texto": "{texto}", "categoria": "gostos"}}',
            contexto,
        )

    resultado = await executar_ferramenta(
        "esquecer",
        '{"texto": "Gosta de jazz e blues", "confirmado": true}',
        contexto,
    )

    assert resultado["ok"] is True
    assert [m["texto"] for m in await banco.listar_memorias("maria")] == [
        "Gosta de jazz"
    ]
