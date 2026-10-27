from __future__ import annotations

import re
from datetime import date
from typing import Sequence

from . import render
from .errors import AjusteInvalido, MemoriaInvalida, ParametroInvalido, PessoaInvalida
from .models import (
    AjusteAprendido,
    Aviso,
    Bloco,
    Camada,
    CategoriaFato,
    Fato,
    FaixaEtaria,
    Formalidade,
    KnobsEfetivos,
    MemoriaDaPessoa,
    NivelSarcasmo,
    NivelTecnico,
    OrigemAjuste,
    Perfil,
    Pessoa,
    Personality,
    PromptMontado,
    TipoAjuste,
    ToqueYandere,
    Trecho,
)

MAX_AJUSTES = 20

_KNOB_ENUM: dict[str, type] = {
    "nivel_sarcasmo": NivelSarcasmo,
    "formalidade": Formalidade,
    "nivel_tecnico": NivelTecnico,
    "toque_yandere": ToqueYandere,
}

_TIPOS_TEXTO = {
    TipoAjuste.APELIDO,
    TipoAjuste.PIADA_INTERNA,
    TipoAjuste.FORMATO,
    TipoAjuste.ASSUNTO,
}

_TETOS = {
    NivelSarcasmo: NivelSarcasmo.MEDIO,
    Formalidade: Formalidade.ALTA,
    NivelTecnico: NivelTecnico.ALTO,
    ToqueYandere: ToqueYandere.LEVE,
}

_CAPS_MENOR = {
    NivelSarcasmo: NivelSarcasmo.LEVE,
    ToqueYandere: ToqueYandere.DESLIGADO,
}

_PRESET_POR_PERFIL = {
    Perfil.PADRAO: "padrao",
    Perfil.CRIANCA_ADOLESCENTE: "perfil_crianca_adolescente",
    Perfil.IDOSO_OU_POUCO_TECNICO: "perfil_idoso_ou_pouco_tecnico",
}

_ROTULOS_CATEGORIA = {
    CategoriaFato.FAMILIA: "família",
    CategoriaFato.TRABALHO: "trabalho",
    CategoriaFato.GOSTOS: "gostos",
    CategoriaFato.ROTINA: "rotina",
    CategoriaFato.SAUDE: "saúde",
    CategoriaFato.OUTRO: "outro",
}

_PADROES_SEGREDO = (
    re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
    re.compile(r"\b(?:\d[ -]?){13,19}\b"),
    re.compile(
        r"\b(senha|password|passwd|pin|cvv|token|chave de acesso|"
        r"conta banc[aá]ria|ag[eê]ncia)\b",
        re.IGNORECASE,
    ),
)

_TITULOS = {
    Camada.LIMITES: "# LIMITES INVIOLÁVEIS",
    Camada.BASE: "# PERSONALIDADE",
    Camada.AJUSTES: "# AJUSTES APRENDIDOS",
    Camada.MEMORIA: "# SOBRE A PESSOA",
    Camada.CONTEXTO: "# TRECHOS DAS NOTAS",
    Camada.REFORCO: "# LEMBRETE FINAL",
}


def montar(
    personality: Personality,
    pessoa: Pessoa,
    ajustes: Sequence[AjusteAprendido] = (),
    memoria: MemoriaDaPessoa | None = None,
    trechos: Sequence[Trecho] = (),
    *,
    max_chars_ajustes: int = 1200,
    max_chars_memoria: int = 2400,
    max_chars_contexto: int = 6000,
) -> PromptMontado:
    if not isinstance(personality, Personality):
        raise ParametroInvalido(
            "personality precisa vir de carregar_personality()"
        )
    if (
        max_chars_ajustes <= 0
        or max_chars_memoria <= 0
        or max_chars_contexto <= 0
    ):
        raise ParametroInvalido("os orçamentos em caracteres precisam ser positivos")

    pessoa = _validar_pessoa(pessoa)
    avisos: list[Aviso] = []

    ajustes_validados = validar_ajustes(ajustes)
    ajustes_validados, aviso = _limitar_quantidade(ajustes_validados)
    if aviso:
        avisos.append(aviso)

    knobs, avisos_knobs = _resolver_knobs(personality, pessoa, ajustes_validados)
    avisos.extend(avisos_knobs)

    ajustes_render, aviso = _cortar_ajustes(
        ajustes_validados, max_chars_ajustes, knobs
    )
    if aviso:
        avisos.append(aviso)

    memoria_normalizada, avisos_memoria = _normalizar_memoria(memoria)
    avisos.extend(avisos_memoria)

    fatos, aviso = _selecionar_fatos(memoria_normalizada.fatos, max_chars_memoria)
    if aviso:
        avisos.append(aviso)

    trechos_validados = _validar_trechos(trechos)
    trechos_render, aviso = _cortar_trechos(
        trechos_validados, max_chars_contexto
    )
    if aviso:
        avisos.append(aviso)

    blocos = [
        Bloco(
            Camada.LIMITES,
            _TITULOS[Camada.LIMITES],
            render.render_limites(personality.limites_inviolaveis),
        ),
        Bloco(
            Camada.BASE,
            _TITULOS[Camada.BASE],
            render.render_base(personality, knobs),
        ),
    ]
    if ajustes_render:
        blocos.append(
            Bloco(
                Camada.AJUSTES,
                _TITULOS[Camada.AJUSTES],
                render.render_ajustes(ajustes_render, knobs),
            )
        )
    if fatos or memoria_normalizada.nao_mencionar:
        blocos.append(
            Bloco(
                Camada.MEMORIA,
                _TITULOS[Camada.MEMORIA],
                render.render_memoria(
                    pessoa.nome, fatos, memoria_normalizada.nao_mencionar
                ),
            )
        )
    if trechos_render:
        blocos.append(
            Bloco(
                Camada.CONTEXTO,
                _TITULOS[Camada.CONTEXTO],
                render.render_contexto(trechos_render),
            )
        )
    blocos.append(
        Bloco(Camada.REFORCO, _TITULOS[Camada.REFORCO], render.render_reforco())
    )

    return PromptMontado(
        blocos=tuple(blocos),
        knobs=knobs,
        avisos=tuple(avisos),
    )


def _validar_pessoa(pessoa: Pessoa) -> Pessoa:
    if not isinstance(pessoa, Pessoa):
        raise PessoaInvalida("pessoa precisa ser uma instância de Pessoa")
    nome = pessoa.nome.strip() if isinstance(pessoa.nome, str) else ""
    if not nome:
        raise PessoaInvalida("o nome da pessoa é obrigatório")
    try:
        faixa = FaixaEtaria(pessoa.faixa_etaria)
    except (TypeError, ValueError) as erro:
        raise PessoaInvalida(
            "faixa_etaria é obrigatória e precisa ser adulto, adolescente ou crianca"
        ) from erro
    try:
        perfil = Perfil(pessoa.perfil)
    except (TypeError, ValueError) as erro:
        raise PessoaInvalida(f"perfil inválido: {pessoa.perfil!r}") from erro
    return Pessoa(nome=nome, faixa_etaria=faixa, perfil=perfil)


def validar_ajustes(
    ajustes: Sequence[AjusteAprendido],
) -> list[AjusteAprendido]:
    validados: list[AjusteAprendido] = []
    for indice, ajuste in enumerate(ajustes):
        if not isinstance(ajuste, AjusteAprendido):
            raise AjusteInvalido(f"ajuste #{indice} não é um AjusteAprendido")
        try:
            tipo = TipoAjuste(ajuste.tipo)
        except (TypeError, ValueError) as erro:
            raise AjusteInvalido(
                f"ajuste #{indice} tem tipo inválido: {ajuste.tipo!r}"
            ) from erro
        try:
            origem = OrigemAjuste(ajuste.origem)
        except (TypeError, ValueError) as erro:
            raise AjusteInvalido(
                f"ajuste #{indice} tem origem inválida: {ajuste.origem!r}"
            ) from erro

        texto = ajuste.texto.strip() if isinstance(ajuste.texto, str) else ""
        valor = ajuste.valor.strip() if isinstance(ajuste.valor, str) else ""

        if tipo in _TIPOS_TEXTO:
            if not texto:
                raise AjusteInvalido(f"ajuste #{indice} ({tipo.value}) exige texto")
        elif tipo.value in _KNOB_ENUM:
            if not valor:
                raise AjusteInvalido(f"ajuste #{indice} ({tipo.value}) exige valor")
            _validar_valor_knob(tipo.value, valor, indice)
        else:
            raise AjusteInvalido(f"ajuste #{indice} tem tipo desconhecido: {tipo!r}")

        validados.append(
            AjusteAprendido(
                tipo=tipo,
                texto=texto or None,
                valor=valor or None,
                origem=origem,
                criado_em=ajuste.criado_em,
            )
        )
    return validados


def _validar_valor_knob(tipo: str, valor: str, indice: int) -> None:
    enum = _KNOB_ENUM[tipo]
    try:
        enum(valor)
    except (TypeError, ValueError) as erro:
        permitidos = ", ".join(membro.value for membro in enum)
        raise AjusteInvalido(
            f"ajuste #{indice} ({tipo}) tem valor inválido: {valor!r}; "
            f"permitidos: {permitidos}"
        ) from erro


def _limitar_quantidade(
    ajustes: list[AjusteAprendido],
) -> tuple[list[AjusteAprendido], Aviso | None]:
    if len(ajustes) <= MAX_AJUSTES:
        return ajustes, None
    mantidos = ajustes[-MAX_AJUSTES:]
    aviso = Aviso(
        "ajustes_demais",
        f"{len(ajustes)} ajustes recebidos; mantidos os {MAX_AJUSTES} mais recentes.",
    )
    return mantidos, aviso


def _resolver_knobs(
    personality: Personality,
    pessoa: Pessoa,
    ajustes: Sequence[AjusteAprendido],
) -> tuple[KnobsEfetivos, list[Aviso]]:
    avisos: list[Aviso] = []
    adaptacao = personality.adaptacao_por_usuario
    base = adaptacao["padrao"]
    perfil = _perfil_efetivo(pessoa, avisos)
    preset = adaptacao.get(_PRESET_POR_PERFIL[perfil]) or {}

    valores: dict[str, str] = {chave: base[chave] for chave in _KNOB_ENUM}
    for chave in _KNOB_ENUM:
        if chave in preset:
            valores[chave] = preset[chave]
    for ajuste in ajustes:
        if ajuste.tipo.value in _KNOB_ENUM:
            valores[ajuste.tipo.value] = ajuste.valor

    menor = pessoa.faixa_etaria in (FaixaEtaria.CRIANCA, FaixaEtaria.ADOLESCENTE)

    efetivos: dict[str, object] = {}
    for chave, enum in _KNOB_ENUM.items():
        valor = enum(valores[chave])
        valor, clampado = _aplicar_teto(enum, valor, menor)
        if clampado:
            avisos.append(
                Aviso(
                    "ajuste_clampado",
                    f"{chave} limitado a {valor.value} pelo teto da base"
                    + (" ou pela faixa etária" if menor else ""),
                )
            )
        efetivos[chave] = valor

    tamanho = preset.get("tamanho_respostas") or base["tamanho_respostas"]
    tom_extra = preset.get("tom")
    return (
        KnobsEfetivos(
            nivel_sarcasmo=efetivos["nivel_sarcasmo"],
            formalidade=efetivos["formalidade"],
            nivel_tecnico=efetivos["nivel_tecnico"],
            toque_yandere=efetivos["toque_yandere"],
            tamanho_respostas=str(tamanho),
            tom_extra=str(tom_extra) if tom_extra else None,
        ),
        avisos,
    )


def _perfil_efetivo(pessoa: Pessoa, avisos: list[Aviso]) -> Perfil:
    if pessoa.faixa_etaria in (FaixaEtaria.CRIANCA, FaixaEtaria.ADOLESCENTE):
        if pessoa.perfil not in (Perfil.PADRAO, Perfil.CRIANCA_ADOLESCENTE):
            avisos.append(
                Aviso(
                    "perfil_sobrescrito",
                    f"perfil {pessoa.perfil.value} substituído por "
                    f"crianca_adolescente porque a faixa etária é "
                    f"{pessoa.faixa_etaria.value}",
                )
            )
        return Perfil.CRIANCA_ADOLESCENTE
    return pessoa.perfil


def _aplicar_teto(
    enum: type, valor: object, menor: bool
) -> tuple[object, bool]:
    ordem = tuple(enum)
    limite = _TETOS[enum]
    if menor and enum in _CAPS_MENOR:
        candidato = _CAPS_MENOR[enum]
        if ordem.index(candidato) < ordem.index(limite):
            limite = candidato
    if ordem.index(valor) > ordem.index(limite):
        return limite, True
    return valor, False


def _cortar_ajustes(
    ajustes: list[AjusteAprendido], orcamento: int, knobs: KnobsEfetivos
) -> tuple[list[AjusteAprendido], Aviso | None]:
    if not ajustes or len(render.render_ajustes(ajustes, knobs)) <= orcamento:
        return ajustes, None

    atual = list(ajustes)
    removidos = 0
    while atual and len(render.render_ajustes(atual, knobs)) > orcamento:
        indice = next(
            (i for i, ajuste in enumerate(atual) if ajuste.tipo in _TIPOS_TEXTO),
            None,
        )
        if indice is None:
            break
        atual.pop(indice)
        removidos += 1

    if not removidos:
        return atual, None
    return atual, Aviso(
        "ajustes_truncados",
        f"{removidos} ajuste(s) de texto não couberam em {orcamento} caracteres.",
    )


def _normalizar_memoria(
    memoria: MemoriaDaPessoa | None,
) -> tuple[MemoriaDaPessoa, list[Aviso]]:
    if memoria is None:
        return MemoriaDaPessoa(), []
    if not isinstance(memoria, MemoriaDaPessoa):
        raise MemoriaInvalida("memoria precisa ser uma instância de MemoriaDaPessoa")

    avisos: list[Aviso] = []
    silenciados = memoria.nao_mencionar
    termos = [termo.strip() for termo in silenciados if termo and termo.strip()]

    fatos: list[Fato] = []
    segredos = 0
    filtrados = 0
    for fato in memoria.fatos:
        if (
            not isinstance(fato, Fato)
            or not isinstance(fato.texto, str)
            or not fato.texto.strip()
        ):
            raise MemoriaInvalida("todo fato precisa ter texto")
        try:
            categoria = CategoriaFato(fato.categoria)
        except (TypeError, ValueError) as erro:
            raise MemoriaInvalida(
                f"categoria de fato inválida: {fato.categoria!r}"
            ) from erro

        if contem_segredo(fato.texto):
            segredos += 1
            continue
        if any(termo.casefold() in fato.texto.casefold() for termo in termos):
            filtrados += 1
            continue

        fatos.append(
            Fato(
                texto=fato.texto.strip(),
                categoria=categoria,
                criado_em=fato.criado_em,
            )
        )

    if segredos:
        avisos.append(
            Aviso(
                "fato_segredo_removido",
                f"{segredos} fato(s) removido(s) por parecer conter dado sensível.",
            )
        )
    if filtrados:
        avisos.append(
            Aviso(
                "fato_silenciado",
                f"{filtrados} fato(s) omitido(s) por estar(em) em nao_mencionar.",
            )
        )

    return (
        MemoriaDaPessoa(fatos=tuple(fatos), nao_mencionar=tuple(termos)),
        avisos,
    )


def _selecionar_fatos(
    fatos: Sequence[Fato], orcamento: int
) -> tuple[list[str], Aviso | None]:
    ordenados = sorted(
        fatos,
        key=lambda fato: (
            fato.criado_em is not None,
            fato.criado_em or date.min,
        ),
        reverse=True,
    )

    linhas: list[str] = []
    for fato in ordenados:
        linha = f"[{_ROTULOS_CATEGORIA[fato.categoria]}] {fato.texto}"
        if len("\n".join(linhas + [linha])) > orcamento:
            break
        linhas.append(linha)

    cortados = len(ordenados) - len(linhas)
    if not cortados:
        return linhas, None
    return linhas, Aviso(
        "memoria_truncada",
        f"{cortados} fato(s) não couberam em {orcamento} caracteres.",
    )


def contem_segredo(texto: str) -> bool:
    return any(padrao.search(texto) for padrao in _PADROES_SEGREDO)


def _validar_trechos(trechos: Sequence[Trecho]) -> list[Trecho]:
    validados: list[Trecho] = []
    for indice, trecho in enumerate(trechos):
        if not isinstance(trecho, Trecho):
            raise ParametroInvalido(f"trecho #{indice} não é um Trecho")
        nota = trecho.nota.strip() if isinstance(trecho.nota, str) else ""
        texto = trecho.texto.strip() if isinstance(trecho.texto, str) else ""
        if not nota or not texto:
            raise ParametroInvalido(
                f"trecho #{indice} precisa de nota e texto não vazios"
            )
        secao = trecho.secao.strip() if isinstance(trecho.secao, str) else ""
        validados.append(Trecho(nota=nota, secao=secao, texto=texto))
    return validados


def _cortar_trechos(
    trechos: list[Trecho], orcamento: int
) -> tuple[list[Trecho], Aviso | None]:
    if not trechos or len(render.render_contexto(trechos)) <= orcamento:
        return trechos, None

    mantidos: list[Trecho] = []
    total = len(render.render_contexto(()))
    for trecho in trechos:
        custo = len(trecho.texto) + len(trecho.nota) + len(trecho.secao) + 8
        if total + custo > orcamento:
            continue
        mantidos.append(trecho)
        total += custo

    descartados = len(trechos) - len(mantidos)
    if not descartados:
        return trechos, None
    return mantidos, Aviso(
        "contexto_truncado",
        f"{descartados} trecho(s) de nota não couberam em "
        f"{orcamento} caracteres.",
    )
