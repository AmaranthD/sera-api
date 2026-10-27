from __future__ import annotations

import pytest

from sera.prompt import (
    Camada,
    FaixaEtaria,
    ParametroInvalido,
    Pessoa,
    Trecho,
    montar,
)

ADULTO = Pessoa(nome="Maria", faixa_etaria=FaixaEtaria.ADULTO)


def test_contexto_entra_entre_memoria_e_reforco(personality):
    resultado = montar(
        personality,
        ADULTO,
        trechos=[Trecho("Sera", "Visão", "base de conhecimento")],
    )
    assert resultado.camadas == (
        Camada.LIMITES,
        Camada.BASE,
        Camada.CONTEXTO,
        Camada.REFORCO,
    )


def test_sem_trechos_omite_a_camada(personality):
    assert Camada.CONTEXTO not in montar(personality, ADULTO).camadas


def test_contexto_agrupa_trechos_da_mesma_nota(personality):
    resultado = montar(
        personality,
        ADULTO,
        trechos=[
            Trecho("Sera", "Visão", "base de conhecimento"),
            Trecho("Sera", "Fases", "MVP"),
            Trecho("Web", "PWA", "shell offline"),
        ],
    )
    conteudo = resultado.blocos[-2].conteudo
    assert conteudo.count("### [[Sera]]") == 1
    assert "**Visão**\nbase de conhecimento" in conteudo
    assert "### [[Web]]" in conteudo


def test_contexto_nao_colapsa_as_linhas_da_nota(personality):
    resultado = montar(
        personality,
        ADULTO,
        trechos=[Trecho("Sera", "", "- um\n- dois")],
    )
    assert "- um\n- dois" in resultado.blocos[-2].conteudo


def test_trecho_sem_secao_renderiza_so_o_titulo(personality):
    resultado = montar(
        personality, ADULTO, trechos=[Trecho("Nota", "", "texto")]
    )
    assert resultado.blocos[-2].conteudo.endswith("### [[Nota]]\ntexto")


def test_contexto_respeita_orcamento_e_avisa(personality):
    trechos = [
        Trecho(f"Nota {indice}", "Seção", "x" * 400) for indice in range(10)
    ]
    resultado = montar(
        personality, ADULTO, trechos=trechos, max_chars_contexto=1000
    )
    assert [aviso.codigo for aviso in resultado.avisos] == ["contexto_truncado"]
    mantidos = resultado.blocos[-2].conteudo.count("### [[")
    assert 1 <= mantidos < len(trechos)


def test_contexto_cabe_inteiro_nao_avisa(personality):
    resultado = montar(
        personality,
        ADULTO,
        trechos=[Trecho("Nota", "Seção", "texto curto")],
        max_chars_contexto=6000,
    )
    assert resultado.avisos == ()


def test_trecho_invalido_e_recusado(personality):
    with pytest.raises(ParametroInvalido):
        montar(personality, ADULTO, trechos=[Trecho("", "Seção", "texto")])
    with pytest.raises(ParametroInvalido):
        montar(personality, ADULTO, trechos=[Trecho("Nota", "Seção", "  ")])


def test_orcamento_de_contexto_precisa_ser_positivo(personality):
    with pytest.raises(ParametroInvalido):
        montar(personality, ADULTO, max_chars_contexto=0)
