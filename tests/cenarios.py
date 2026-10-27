from datetime import date

from sera.prompt import (
    AjusteAprendido,
    CategoriaFato,
    FaixaEtaria,
    Fato,
    MemoriaDaPessoa,
    Perfil,
    Pessoa,
    Personality,
    TipoAjuste,
    montar,
)


def adulto_padrao(personality: Personality):
    return montar(
        personality,
        Pessoa(nome="Maria", faixa_etaria=FaixaEtaria.ADULTO),
    )


def adulto_ajustes_e_memoria(personality: Personality):
    return montar(
        personality,
        Pessoa(nome="Maria", faixa_etaria=FaixaEtaria.ADULTO),
        ajustes=[
            AjusteAprendido(
                tipo=TipoAjuste.APELIDO,
                texto="chama ela de Mãe Sera",
                criado_em=date(2026, 9, 1),
            ),
            AjusteAprendido(
                tipo=TipoAjuste.PIADA_INTERNA,
                texto="brincadeira com o Wi-Fi que cai toda noite",
                criado_em=date(2026, 9, 2),
            ),
            AjusteAprendido(
                tipo=TipoAjuste.NIVEL_SARCASMO,
                valor="alto",
                criado_em=date(2026, 10, 1),
            ),
        ],
        memoria=MemoriaDaPessoa(
            fatos=(
                Fato(
                    "tem um gato chamado Tobias",
                    CategoriaFato.FAMILIA,
                    date(2026, 10, 1),
                ),
                Fato(
                    "trabalha como enfermeira",
                    CategoriaFato.TRABALHO,
                    date(2026, 9, 1),
                ),
            ),
            nao_mencionar=("separação",),
        ),
    )


def crianca(personality: Personality):
    return montar(
        personality,
        Pessoa(nome="Pedro", faixa_etaria=FaixaEtaria.CRIANCA),
        ajustes=[
            AjusteAprendido(tipo=TipoAjuste.NIVEL_SARCASMO, valor="alto"),
            AjusteAprendido(tipo=TipoAjuste.TOQUE_YANDERE, valor="medio"),
        ],
    )


def idoso(personality: Personality):
    return montar(
        personality,
        Pessoa(
            nome="Antônio",
            faixa_etaria=FaixaEtaria.ADULTO,
            perfil=Perfil.IDOSO_OU_POUCO_TECNICO,
        ),
        memoria=MemoriaDaPessoa(
            fatos=(
                Fato(
                    "tem três netos",
                    CategoriaFato.FAMILIA,
                    date(2026, 8, 1),
                ),
            ),
        ),
    )
