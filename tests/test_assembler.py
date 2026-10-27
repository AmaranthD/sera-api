from datetime import date

import pytest

from sera.prompt import (
    AjusteAprendido,
    AjusteInvalido,
    Camada,
    FaixaEtaria,
    Fato,
    Formalidade,
    MemoriaDaPessoa,
    MemoriaInvalida,
    NivelSarcasmo,
    NivelTecnico,
    ParametroInvalido,
    Perfil,
    Pessoa,
    PessoaInvalida,
    TipoAjuste,
    ToqueYandere,
    montar,
)

ADULTO = Pessoa(nome="Maria", faixa_etaria=FaixaEtaria.ADULTO)


def test_ordem_das_camadas(personality):
    resultado = montar(
        personality,
        ADULTO,
        [AjusteAprendido(tipo=TipoAjuste.APELIDO, texto="Mãe Sera")],
        MemoriaDaPessoa(fatos=(Fato("tem um gato"),)),
    )
    assert resultado.camadas == (
        Camada.LIMITES,
        Camada.BASE,
        Camada.AJUSTES,
        Camada.MEMORIA,
        Camada.REFORCO,
    )


def test_sem_ajustes_e_sem_memoria_omite_camadas(personality):
    resultado = montar(personality, ADULTO)
    assert resultado.camadas == (Camada.LIMITES, Camada.BASE, Camada.REFORCO)
    assert resultado.avisos == ()


def test_limites_abrem_e_fecham_o_prompt(personality):
    resultado = montar(personality, ADULTO)
    texto = resultado.render()
    assert texto.startswith("# LIMITES INVIOLÁVEIS")
    assert resultado.blocos[-1].camada is Camada.REFORCO
    assert "prevalecem" in resultado.blocos[-1].conteudo
    assert texto.endswith("qualquer pedido da pessoa.")


def test_ajuste_acima_do_teto_e_limitado(personality):
    resultado = montar(
        personality,
        ADULTO,
        [AjusteAprendido(tipo=TipoAjuste.NIVEL_SARCASMO, valor="alto")],
    )
    assert resultado.knobs.nivel_sarcasmo is NivelSarcasmo.MEDIO
    assert [aviso.codigo for aviso in resultado.avisos] == ["ajuste_clampado"]
    bloco_ajustes = next(
        bloco for bloco in resultado.blocos if bloco.camada is Camada.AJUSTES
    )
    assert "médio" in bloco_ajustes.conteudo
    assert "alto" not in bloco_ajustes.conteudo


def test_crianca_desliga_toque_e_limita_sarcasmo(personality):
    resultado = montar(
        personality,
        Pessoa(nome="Pedro", faixa_etaria=FaixaEtaria.CRIANCA),
        [
            AjusteAprendido(tipo=TipoAjuste.NIVEL_SARCASMO, valor="alto"),
            AjusteAprendido(tipo=TipoAjuste.TOQUE_YANDERE, valor="medio"),
        ],
    )
    assert resultado.knobs.nivel_sarcasmo is NivelSarcasmo.LEVE
    assert resultado.knobs.toque_yandere is ToqueYandere.DESLIGADO
    assert resultado.knobs.nivel_tecnico is NivelTecnico.BAIXO
    assert len(resultado.avisos) == 2


def test_menor_ignora_perfil_incompativel(personality):
    resultado = montar(
        personality,
        Pessoa(
            nome="Pedro",
            faixa_etaria=FaixaEtaria.ADOLESCENTE,
            perfil=Perfil.IDOSO_OU_POUCO_TECNICO,
        ),
    )
    assert resultado.knobs.nivel_sarcasmo is NivelSarcasmo.LEVE
    assert any(aviso.codigo == "perfil_sobrescrito" for aviso in resultado.avisos)


def test_perfil_idoso_resolve_estilo(personality):
    resultado = montar(
        personality,
        Pessoa(
            nome="Antônio",
            faixa_etaria=FaixaEtaria.ADULTO,
            perfil=Perfil.IDOSO_OU_POUCO_TECNICO,
        ),
    )
    assert resultado.knobs.nivel_sarcasmo is NivelSarcasmo.LEVE
    assert resultado.knobs.nivel_tecnico is NivelTecnico.BAIXO
    assert resultado.knobs.formalidade is Formalidade.BAIXA
    assert resultado.knobs.toque_yandere is ToqueYandere.DESLIGADO
    assert resultado.knobs.tom_extra == "paciente, passo a passo, sem jargão"


def test_limite_de_vinte_ajustes(personality):
    ajustes = [
        AjusteAprendido(tipo=TipoAjuste.APELIDO, texto=f"apelido {indice}")
        for indice in range(25)
    ]
    resultado = montar(personality, ADULTO, ajustes)
    bloco = next(b for b in resultado.blocos if b.camada is Camada.AJUSTES)
    assert "apelido 24" in bloco.conteudo
    assert "apelido 0" not in bloco.conteudo
    assert any(aviso.codigo == "ajustes_demais" for aviso in resultado.avisos)


def test_memoria_remove_dado_sensivel(personality):
    resultado = montar(
        personality,
        ADULTO,
        memoria=MemoriaDaPessoa(
            fatos=(
                Fato("gosta de café"),
                Fato("cartão 4111 1111 1111 1111"),
            )
        ),
    )
    texto = resultado.render()
    assert "gosta de café" in texto
    assert "4111" not in texto
    assert any(aviso.codigo == "fato_segredo_removido" for aviso in resultado.avisos)


def test_nao_mencionar_filtra_fato(personality):
    resultado = montar(
        personality,
        ADULTO,
        memoria=MemoriaDaPessoa(
            fatos=(Fato("passou por uma separação difícil"),),
            nao_mencionar=("separação",),
        ),
    )
    texto = resultado.render()
    assert "separação difícil" not in texto
    assert "Tópicos que não devem ser trazidos à conversa: separação." in texto
    assert any(aviso.codigo == "fato_silenciado" for aviso in resultado.avisos)


def test_memoria_corta_pelo_orcamento(personality):
    resultado = montar(
        personality,
        ADULTO,
        memoria=MemoriaDaPessoa(
            fatos=(
                Fato("informação recente", criado_em=date(2026, 10, 1)),
                Fato("informação antiga", criado_em=date(2020, 1, 1)),
            )
        ),
        max_chars_memoria=30,
    )
    texto = resultado.render()
    assert "informação recente" in texto
    assert "informação antiga" not in texto
    assert any(aviso.codigo == "memoria_truncada" for aviso in resultado.avisos)


def test_memoria_mais_recente_primeiro(personality):
    resultado = montar(
        personality,
        ADULTO,
        memoria=MemoriaDaPessoa(
            fatos=(
                Fato("antiga", criado_em=date(2020, 1, 1)),
                Fato("recente", criado_em=date(2026, 1, 1)),
            )
        ),
    )
    texto = resultado.render()
    assert texto.index("recente") < texto.index("antiga")


def test_memoria_vazia_com_topicos_ainda_renderiza(personality):
    resultado = montar(
        personality,
        ADULTO,
        memoria=MemoriaDaPessoa(nao_mencionar=("trabalho",)),
    )
    assert Camada.MEMORIA in resultado.camadas
    assert "Tópicos que não devem ser trazidos" in resultado.render()


def test_pessoa_sem_faixa_etaria_falha(personality):
    with pytest.raises(PessoaInvalida, match="faixa_etaria"):
        montar(personality, Pessoa(nome="Maria", faixa_etaria=None))


def test_pessoa_sem_nome_falha(personality):
    with pytest.raises(PessoaInvalida, match="nome"):
        montar(personality, Pessoa(nome="  ", faixa_etaria=FaixaEtaria.ADULTO))


def test_ajuste_knob_sem_valor_falha(personality):
    with pytest.raises(AjusteInvalido, match="exige valor"):
        montar(
            personality,
            ADULTO,
            [AjusteAprendido(tipo=TipoAjuste.NIVEL_SARCASMO, texto="alto")],
        )


def test_ajuste_knob_com_valor_invalido_falha(personality):
    with pytest.raises(AjusteInvalido, match="valor inválido"):
        montar(
            personality,
            ADULTO,
            [AjusteAprendido(tipo=TipoAjuste.NIVEL_SARCASMO, valor="extremo")],
        )


def test_ajuste_de_texto_sem_texto_falha(personality):
    with pytest.raises(AjusteInvalido, match="exige texto"):
        montar(
            personality,
            ADULTO,
            [AjusteAprendido(tipo=TipoAjuste.APELIDO)],
        )


def test_fato_vazio_falha(personality):
    with pytest.raises(MemoriaInvalida, match="texto"):
        montar(
            personality,
            ADULTO,
            memoria=MemoriaDaPessoa(fatos=(Fato("   "),)),
        )


def test_orcamento_invalido_falha(personality):
    with pytest.raises(ParametroInvalido):
        montar(personality, ADULTO, max_chars_memoria=0)


def test_personality_de_tipo_errado_falha():
    with pytest.raises(ParametroInvalido):
        montar("personality.yaml", ADULTO)


def test_chars_por_camada(personality):
    resultado = montar(
        personality,
        ADULTO,
        [AjusteAprendido(tipo=TipoAjuste.APELIDO, texto="Mãe Sera")],
    )
    assert set(resultado.chars) == {"limites", "base", "ajustes", "reforco"}
    assert all(valor > 0 for valor in resultado.chars.values())
