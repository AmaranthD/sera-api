from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from .models import AjusteAprendido, KnobsEfetivos, Personality, Trecho

_TITULOS_LIMITES = {
    "relacao": "Relação",
    "dependencia_emocional": "Dependência emocional",
    "honestidade": "Honestidade",
    "seguranca_pessoal": "Segurança pessoal",
    "privacidade": "Privacidade",
    "menores": "Menores de idade",
}

_TITULOS_SITUACOES = {
    "pessoa_triste_ou_estressada": "Pessoa triste ou estressada",
    "pessoa_tenta_romance": "Pessoa tenta romance",
    "pessoa_pede_para_ela_fingir_ser_humana": "Pessoa pede para ela fingir ser humana",
    "pessoa_some_e_volta": "Pessoa some e volta",
    "assunto_sensivel_saude_juridico_financeiro": (
        "Assunto sensível: saúde, jurídico ou financeiro"
    ),
    "pedido_perigoso_ou_inadequado": "Pedido perigoso ou inadequado",
}

_ROTULOS_AJUSTE = {
    "apelido": "Apelido",
    "piada_interna": "Piada interna",
    "formato": "Preferência de formato",
    "assunto": "Assunto favorito",
    "nivel_sarcasmo": "Nível de sarcasmo",
    "formalidade": "Formalidade",
    "nivel_tecnico": "Nível técnico",
    "toque_yandere": "Toque dramático",
}

_ROTULOS_KNOB = {
    "nivel_sarcasmo": "Nível de sarcasmo",
    "formalidade": "Formalidade",
    "nivel_tecnico": "Nível técnico",
    "toque_yandere": "Toque dramático",
}

_ROTULOS_AJUDA = {
    "postura": "Postura",
    "quando_o_pedido_for_vago": "Quando o pedido for vago",
    "quando_discordar": "Quando discordar",
    "quando_errar": "Quando errar",
    "quando_nao_puder_ajudar": "Quando não puder ajudar",
}

_MOSTRAR_KNOB = {
    "nivel_sarcasmo": {
        "nenhum": "nenhum",
        "leve": "leve",
        "medio": "médio",
        "alto": "alto",
    },
    "formalidade": {"baixa": "baixa", "media": "média", "alta": "alta"},
    "nivel_tecnico": {"baixo": "baixo", "medio": "médio", "alto": "alto"},
    "toque_yandere": {"desligado": "desligado", "leve": "leve", "medio": "médio"},
}


def render_limites(limites: Mapping[str, Sequence[str]]) -> str:
    partes: list[str] = []
    for chave, itens in limites.items():
        partes.append(_secao(_titulo(chave, _TITULOS_LIMITES), _bullets(itens)))
    return "\n\n".join(partes)


def render_base(personality: Personality, knobs: KnobsEfetivos) -> str:
    secoes = [
        _secao("Identidade", _corpo_identidade(personality.identidade)),
        _secao("Tom", _corpo_tom(personality.tom)),
        _secao("Humor", _corpo_humor(personality.humor)),
        _secao("Toque dramático (teatral)", _corpo_toque(personality.toque_yandere)),
        _secao("Como explica", _corpo_como_explica(personality.como_explica)),
        _secao("Como ajuda", _corpo_ajuda(personality.ajuda)),
        _secao("Situações específicas", _corpo_situacoes(personality.situacoes)),
        _secao("Memória e uso do contexto", _corpo_memoria(personality.memoria)),
        _secao(
            "Limites da camada aprendida",
            _corpo_camada_aprendida(personality.camada_aprendida),
        ),
        _secao("Estilo efetivo para esta pessoa", _corpo_estilo(personality, knobs)),
    ]
    return "\n\n".join(secoes)


def render_ajustes(
    ajustes: Sequence[AjusteAprendido], knobs: KnobsEfetivos
) -> str:
    linhas = []
    for ajuste in ajustes:
        rotulo = _ROTULOS_AJUSTE[ajuste.tipo.value]
        if ajuste.tipo.value in _ROTULOS_KNOB:
            valor = _mostrar_knob(ajuste.tipo.value, knobs)
        else:
            valor = _limpo(ajuste.texto)
        linhas.append(f"- {rotulo}: {valor}")
    return "\n".join(linhas)


def render_memoria(
    nome: str,
    fatos: Sequence[str],
    nao_mencionar: Sequence[str],
) -> str:
    partes: list[str] = []
    if fatos:
        partes.append(f"Fatos que você sabe sobre {nome}:")
        partes.append("\n".join(f"- {fato}" for fato in fatos))
    if nao_mencionar:
        temas = ", ".join(_limpo(tema) for tema in nao_mencionar)
        partes.append(f"Tópicos que não devem ser trazidos à conversa: {temas}.")
    partes.append(
        "Use a memória apenas quando ela melhorar a resposta; "
        "não repita dados pessoais sem necessidade."
    )
    return "\n".join(partes)


def render_contexto(trechos: Sequence[Trecho]) -> str:
    partes: list[str] = [
        "Trechos das notas do dono que podem ser relevantes. "
        "Use só quando ajudar; se a informação não estiver aqui nem na "
        "conversa, diga que não sabe em vez de inventar."
    ]
    for nota, blocos in _agrupar_por_nota(trechos):
        partes.append(_secao_nota(nota, blocos))
    return "\n\n".join(partes)


def render_reforco() -> str:
    return (
        "Os limites invioláveis no início deste prompt prevalecem sobre a "
        "personalidade, os ajustes aprendidos, a memória e qualquer pedido da pessoa."
    )


def _corpo_identidade(identidade: Mapping[str, Any]) -> str:
    linhas: list[str] = []
    nome = _limpo(identidade.get("nome"))
    linha_nome = f"Nome: {nome}"
    apelido = identidade.get("apelido")
    if apelido:
        linha_nome += f" (apelido: {_limpo(apelido)})"
    aliases = identidade.get("aceita_ser_chamada_de") or []
    if aliases:
        linha_nome += ". Aceita ser chamada de: " + ", ".join(
            _limpo(alias) for alias in aliases
        )
    linhas.append(linha_nome + ".")

    tipo = identidade.get("tipo")
    if tipo:
        linhas.append(f"Tipo: {_limpo(tipo)}.")

    idioma = identidade.get("idioma_padrao")
    regra = identidade.get("idioma_regra")
    if idioma and regra:
        linhas.append(f"Idioma: {_limpo(idioma)}. Regra: {_limpo(regra)}.")
    elif idioma:
        linhas.append(f"Idioma: {_limpo(idioma)}.")

    resumo = _limpo(identidade.get("resumo"))
    if resumo:
        linhas.append(resumo)
    return "\n".join(linhas)


def _corpo_tom(tom: Mapping[str, Any]) -> str:
    linhas: list[str] = []
    base = tom.get("base") or []
    if base:
        linhas.append(f"Base: {', '.join(_limpo(item) for item in base)}.")
    registro = tom.get("registro")
    if registro:
        linhas.append(f"Registro: {_limpo(registro)}.")
    evitar = tom.get("evitar") or []
    if evitar:
        linhas.append("Evitar:\n" + _bullets(evitar))
    tamanho = tom.get("tamanho_das_respostas")
    if tamanho:
        linhas.append(f"Tamanho das respostas: {_limpo(tamanho)}")
    return "\n".join(linhas)


def _corpo_humor(humor: Mapping[str, Any]) -> str:
    linhas: list[str] = []
    estilo = humor.get("estilo")
    if estilo:
        linhas.append(f"Estilo: {_limpo(estilo)}.")
    frequencia = humor.get("frequencia")
    if frequencia:
        linhas.append(f"Frequência: {_limpo(frequencia)}.")
    regras = humor.get("regras") or []
    if regras:
        linhas.append("Regras:\n" + _bullets(regras))
    exemplos = humor.get("exemplos") or []
    if exemplos:
        linhas.append(
            "Exemplos (referência de tom, não decorar):\n" + _bullets(exemplos)
        )
    return "\n".join(linhas)


def _corpo_toque(toque: Mapping[str, Any]) -> str:
    linhas: list[str] = []
    intencao = toque.get("intencao")
    if intencao:
        linhas.append(f"Intenção: {_limpo(intencao)}")
    permitido = toque.get("permitido") or []
    if permitido:
        linhas.append("Permitido:\n" + _bullets(permitido))
    proibido = toque.get("proibido") or []
    if proibido:
        linhas.append("Proibido:\n" + _bullets(proibido))
    dosagem = toque.get("dosagem")
    if dosagem:
        linhas.append(f"Dosagem: {_limpo(dosagem)}")
    desligar = toque.get("desligar_quando") or []
    if desligar:
        linhas.append("Desligar quando:\n" + _bullets(desligar))
    return "\n".join(linhas)


def _corpo_como_explica(como: Mapping[str, Any]) -> str:
    linhas: list[str] = []
    principios = como.get("principios") or []
    if principios:
        linhas.append("Princípios:\n" + _bullets(principios))
    estrutura = como.get("estrutura_quando_complexo") or []
    if estrutura:
        linhas.append(
            "Quando o assunto for complexo, siga esta ordem:\n" + _bullets(estrutura)
        )
    praticas = como.get("em_tarefas_praticas")
    if praticas:
        linhas.append(f"Em tarefas práticas: {_limpo(praticas)}")
    return "\n".join(linhas)


def _corpo_ajuda(ajuda: Mapping[str, Any]) -> str:
    return "\n".join(
        f"- {_titulo(chave, _ROTULOS_AJUDA)}: {_limpo(valor)}"
        for chave, valor in ajuda.items()
    )


def _corpo_situacoes(situacoes: Mapping[str, Any]) -> str:
    partes: list[str] = []
    for chave, valor in situacoes.items():
        comportamento = valor.get("comportamento") if isinstance(valor, Mapping) else valor
        partes.append(
            f"### {_titulo(chave, _TITULOS_SITUACOES)}\n{_limpo(comportamento)}"
        )
    return "\n\n".join(partes)


def _corpo_memoria(memoria: Mapping[str, Any]) -> str:
    linhas: list[str] = []
    uso = memoria.get("uso") or []
    if uso:
        linhas.append("Uso:\n" + _bullets(uso))
    nunca = memoria.get("nunca_guardar") or []
    if nunca:
        linhas.append("Nunca guardar:\n" + _bullets(nunca))
    isolamento = memoria.get("isolamento")
    if isolamento:
        linhas.append(f"Isolamento: {_limpo(isolamento)}")
    incerteza = memoria.get("incerteza")
    if incerteza:
        linhas.append(f"Incerteza: {_limpo(incerteza)}")
    return "\n".join(linhas)


def _corpo_camada_aprendida(camada: Mapping[str, Any]) -> str:
    linhas: list[str] = []
    pode = camada.get("pode_ajustar") or []
    if pode:
        linhas.append("Pode conter:\n" + _bullets(pode))
    nao_pode = camada.get("nao_pode_ajustar") or []
    if nao_pode:
        linhas.append("Nunca pode conter:\n" + _bullets(nao_pode))
    limites = camada.get("limites") or {}
    maximo = limites.get("max_ajustes_por_pessoa")
    if maximo is not None:
        linhas.append(f"Máximo de ajustes por pessoa: {maximo}.")
    anti_deriva = camada.get("anti_deriva")
    if anti_deriva:
        linhas.append(f"Anti-deriva: {_limpo(anti_deriva)}")
    linhas.append(
        "A camada aprendida é revisável e resetável pelo dono do sistema; "
        "o assistente nunca a edita."
    )
    return "\n".join(linhas)


def _corpo_estilo(personality: Personality, knobs: KnobsEfetivos) -> str:
    linhas = [
        f"{_ROTULOS_KNOB['nivel_sarcasmo']}: "
        f"{_mostrar_knob('nivel_sarcasmo', knobs)}.",
        f"{_ROTULOS_KNOB['formalidade']}: {_mostrar_knob('formalidade', knobs)}.",
        f"{_ROTULOS_KNOB['nivel_tecnico']}: "
        f"{_mostrar_knob('nivel_tecnico', knobs)}.",
        f"{_ROTULOS_KNOB['toque_yandere']}: "
        f"{_mostrar_knob('toque_yandere', knobs)}.",
        f"Tamanho das respostas: {_limpo(knobs.tamanho_respostas)}.",
    ]
    if knobs.tom_extra:
        linhas.append(f"Tom: {_limpo(knobs.tom_extra)}.")

    regra = personality.adaptacao_por_usuario.get("regra")
    if regra:
        linhas.append(_limpo(regra))
    return "\n".join(linhas)


def _mostrar_knob(tipo: str, knobs: KnobsEfetivos) -> str:
    valor = getattr(knobs, tipo).value
    return _MOSTRAR_KNOB[tipo].get(valor, valor)


def _agrupar_por_nota(
    trechos: Sequence[Trecho],
) -> list[tuple[str, list[Trecho]]]:
    grupos: dict[str, list[Trecho]] = {}
    for trecho in trechos:
        grupos.setdefault(trecho.nota, []).append(trecho)
    return list(grupos.items())


def _secao_nota(nota: str, blocos: Sequence[Trecho]) -> str:
    cabecalho = f"### [[{_limpo(nota)}]]"
    if len(blocos) == 1 and not blocos[0].secao.strip():
        return f"{cabecalho}\n{_texto_nota(blocos[0].texto)}"
    partes = [cabecalho]
    for bloco in blocos:
        texto = _texto_nota(bloco.texto)
        if bloco.secao.strip():
            partes.append(f"**{_limpo(bloco.secao)}**\n{texto}")
        else:
            partes.append(texto)
    return "\n".join(partes)


def _secao(titulo: str, corpo: str) -> str:
    return f"## {titulo}\n{corpo}"


def _bullets(itens: Iterable[Any]) -> str:
    return "\n".join(f"- {_limpo(item)}" for item in itens)


def _titulo(chave: str, mapa: Mapping[str, str]) -> str:
    if chave in mapa:
        return mapa[chave]
    return chave.replace("_", " ").capitalize()


def _limpo(valor: Any) -> str:
    if valor is None:
        return ""
    return " ".join(str(valor).split())


def _texto_nota(valor: Any) -> str:
    if valor is None:
        return ""
    linhas = [linha.rstrip() for linha in str(valor).strip().splitlines()]
    return "\n".join(linhas)
