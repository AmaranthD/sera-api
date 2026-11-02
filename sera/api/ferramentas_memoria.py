from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Mapping

from ..prompt import (
    AjusteAprendido,
    AjusteInvalido,
    CategoriaFato,
    OrigemAjuste,
    TipoAjuste,
    contem_segredo,
    validar_ajustes,
)
from .ferramentas_base import (
    ContextoFerramentas,
    FerramentaInvalida,
    NOME_AJUSTAR,
    NOME_ESQUECER,
    NOME_LEMBRAR,
    _MAX_AJUSTES,
    _MAX_MEMORIAS,
    _TAMANHO_MAXIMO_FATO,
    _TAMANHO_MAXIMO_PREFERENCIA,
    _normalizar_texto,
)

_VALORES_KNOB = {
    "nivel_sarcasmo": ("nenhum", "leve", "medio", "alto"),
    "formalidade": ("baixa", "media", "alta"),
    "nivel_tecnico": ("baixo", "medio", "alto"),
    "toque_yandere": ("desligado", "leve", "medio"),
}


ESQUEMA_LEMBRAR = {
    "type": "function",
    "function": {
        "name": NOME_LEMBRAR,
        "description": (
            "Guarda um fato durável sobre a pessoa para usar em conversas "
            "futuras. Use quando ela contar algo que vale lembrar (gostos, "
            "rotina, família, trabalho) ou pedir 'lembre disso'. Não use para "
            "dados sensíveis, opiniões passageiras ou assuntos que ela pediu "
            "para evitar."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "texto": {
                    "type": "string",
                    "description": (
                        "Fato curto, em terceira pessoa, sem senha, cartão, "
                        "documento ou endereço exato."
                    ),
                },
                "categoria": {
                    "type": "string",
                    "enum": [categoria.value for categoria in CategoriaFato],
                },
                "confirmado": {
                    "type": "boolean",
                    "description": (
                        "Use true só depois que a pessoa confirmar. "
                        "Obrigatório na prática para a categoria 'saude'."
                    ),
                },
            },
            "required": ["texto", "categoria"],
        },
    },
}


ESQUEMA_ESQUECER = {
    "type": "function",
    "function": {
        "name": NOME_ESQUECER,
        "description": (
            "Apaga uma memória guardada sobre a pessoa. Use só quando ela "
            "pedir explicitamente para esquecer algo. Sem confirmado=true a "
            "ferramenta não apaga: ela devolve o que encontrou para você "
            "perguntar antes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "texto": {
                    "type": "string",
                    "description": "Trecho do fato que ela quer esquecer.",
                },
                "confirmado": {
                    "type": "boolean",
                    "description": "true só depois do sim da pessoa.",
                },
            },
            "required": ["texto"],
        },
    },
}


ESQUEMA_AJUSTAR = {
    "type": "function",
    "function": {
        "name": NOME_AJUSTAR,
        "description": (
            "Muda uma preferência durável de conversa: apelido, piada "
            "interna, formato, assunto favorito ou nível de formalidade, "
            "sarcasmo, detalhe técnico e drama. Use quando a pessoa pedir "
            "explicitamente para mudar o jeito da conversa."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": [
                        "apelido",
                        "piada_interna",
                        "formato",
                        "assunto",
                        "nivel_sarcasmo",
                        "formalidade",
                        "nivel_tecnico",
                        "toque_yandere",
                    ],
                },
                "texto": {
                    "type": "string",
                    "description": (
                        "Valor textual para apelido, piada interna, formato "
                        "ou assunto. Ex.: 'chamar de Mãe Sera'."
                    ),
                },
                "valor": {
                    "type": "string",
                    "description": (
                        "Para os níveis: nivel_sarcasmo (nenhum|leve|medio|"
                        "alto), formalidade (baixa|media|alta), nivel_tecnico "
                        "(baixo|medio|alto), toque_yandere (desligado|leve|"
                        "medio)."
                    ),
                },
            },
            "required": ["tipo"],
        },
    },
}


INSTRUCAO_MEMORIA = """\
## Memória e preferências

Você pode guardar coisas sobre a pessoa com `lembrar`, mudar preferências
com `ajustar_preferencia` e apagar memórias com `esquecer`.

- Use `lembrar` quando ela contar um fato durável (gostos, rotina, família,
  trabalho) ou pedir "lembre disso".
- Não guarde senhas, cartões, documentos, endereço exato nem opiniões
  passageiras. O sistema recusa dados sensíveis.
- Em assunto sensível (saúde, família, dinheiro), se a pessoa pedir
  explicitamente para lembrar ("lembre que...", "anota isso"), pode guardar.
  Se estiver inferindo o fato sem pedido explícito, pergunte antes. Para
  `saude` o sistema exige `confirmado=true` e um pedido/sim explícito da
  pessoa na mensagem atual; sem isso ele não grava.
- Use `ajustar_preferencia` quando ela pedir para mudar apelido, formato,
  nível de detalhe, formalidade, sarcasmo ou drama.
- Use `esquecer` só quando ela pedir explicitamente para esquecer algo.
  Primeiro chame sem `confirmado`, pergunte ("quer que eu esqueça isso?") e
  só chame de novo com `confirmado=true` depois do sim. Se houver mais de
  uma memória parecida, pergunte qual.
- A agenda é separada da memória: para marcar, consultar ou cancelar
  compromissos use as ferramentas `agendar`, `consultar_agenda` e
  `cancelar_compromisso`.
- Nunca invente memórias. Se não souber, não guarde.
- Depois de guardar ou apagar, confirme em uma frase curta e natural."""


async def _lembrar(
    dados: Mapping, contexto: ContextoFerramentas
) -> dict:
    banco = contexto.banco
    if banco is None or not contexto.pessoa_id:
        raise FerramentaInvalida("a memória não está disponível nesta conversa")

    texto = " ".join(str(dados.get("texto") or "").split())
    if len(texto) < 3:
        raise FerramentaInvalida("o fato está vazio")
    texto = texto[:_TAMANHO_MAXIMO_FATO].rstrip()
    if contem_segredo(texto):
        raise FerramentaInvalida(
            "não posso guardar dados sensíveis como senha, cartão ou documento"
        )

    try:
        categoria = CategoriaFato(
            str(dados.get("categoria") or "outro").strip().lower()
        )
    except ValueError:
        categoria = CategoriaFato.OUTRO

    if categoria is CategoriaFato.SAUDE:
        autorizado = bool(dados.get("confirmado")) and _autorizacao_explicita(
            contexto.mensagem_usuario
        )
        if not autorizado:
            return {
                "ok": False,
                "precisa_confirmar": True,
                "texto": texto,
                "categoria": categoria.value,
            }

    existentes = await banco.listar_memorias(contexto.pessoa_id)
    for memoria in existentes:
        if _normalizar_texto(memoria.get("texto")) == _normalizar_texto(texto):
            return {
                "ok": True,
                "duplicada": True,
                "memoria": {
                    "id": memoria.get("id"),
                    "texto": memoria.get("texto"),
                    "categoria": memoria.get("categoria"),
                },
            }

    if len(existentes) >= _MAX_MEMORIAS:
        raise FerramentaInvalida(
            "a pessoa já tem 100 memórias guardadas; peça para apagar alguma "
            "antes de guardar outra"
        )

    criada = await banco.criar_memoria(
        contexto.pessoa_id, texto, categoria.value
    )
    return {
        "ok": True,
        "memoria": {
            "id": criada.get("id"),
            "texto": criada.get("texto"),
            "categoria": criada.get("categoria"),
        },
    }


async def _ajustar(
    dados: Mapping, contexto: ContextoFerramentas
) -> dict:
    banco = contexto.banco
    if banco is None or not contexto.pessoa_id:
        raise FerramentaInvalida("os ajustes não estão disponíveis nesta conversa")

    tipo = str(dados.get("tipo") or "").strip().lower()
    try:
        TipoAjuste(tipo)
    except ValueError as erro:
        raise FerramentaInvalida(f"tipo de preferência inválido: {tipo!r}") from erro

    texto = " ".join(str(dados.get("texto") or "").split())[
        :_TAMANHO_MAXIMO_PREFERENCIA
    ].rstrip()
    valor = str(dados.get("valor") or "").strip().lower()

    try:
        ajuste = validar_ajustes(
            [
                AjusteAprendido(
                    tipo=TipoAjuste(tipo),
                    texto=texto or None,
                    valor=valor or None,
                    origem=OrigemAjuste.CONVERSA,
                )
            ]
        )[0]
    except AjusteInvalido as erro:
        raise FerramentaInvalida(erro.mensagem) from erro

    existentes = await banco.listar_ajustes(contexto.pessoa_id)

    if ajuste.tipo.value in _VALORES_KNOB:
        for antigo in existentes:
            if antigo.get("tipo") == ajuste.tipo.value:
                await banco.apagar_ajuste(contexto.pessoa_id, antigo["id"])
        existentes = [
            item
            for item in existentes
            if item.get("tipo") != ajuste.tipo.value
        ]
    elif any(
        item.get("tipo") == ajuste.tipo.value
        and _normalizar_texto(item.get("texto"))
        == _normalizar_texto(ajuste.texto)
        for item in existentes
    ):
        return {"ok": True, "duplicado": True}

    if len(existentes) >= _MAX_AJUSTES:
        raise FerramentaInvalida(
            "a pessoa já tem 20 ajustes guardados; peça para remover algum "
            "antes de adicionar outro"
        )

    criado = await banco.criar_ajuste(
        contexto.pessoa_id,
        ajuste.tipo.value,
        ajuste.texto,
        ajuste.valor,
        ajuste.origem.value,
    )
    return {
        "ok": True,
        "ajuste": {
            "id": criado.get("id"),
            "tipo": criado.get("tipo"),
            "texto": criado.get("texto"),
            "valor": criado.get("valor"),
        },
    }


async def _esquecer(
    dados: Mapping, contexto: ContextoFerramentas
) -> dict:
    banco = contexto.banco
    if banco is None or not contexto.pessoa_id:
        raise FerramentaInvalida("a memória não está disponível nesta conversa")

    texto = " ".join(str(dados.get("texto") or "").split())
    if len(texto) < 3:
        raise FerramentaInvalida("diga qual memória deve ser esquecida")

    chave = _normalizar_texto(texto)
    existentes = await banco.listar_memorias(contexto.pessoa_id)
    exatas = [
        memoria
        for memoria in existentes
        if _normalizar_texto(memoria.get("texto")) == chave
    ]
    if len(exatas) == 1:
        candidatas = exatas
    else:
        candidatas = [
            memoria
            for memoria in existentes
            if _parecido(chave, _normalizar_texto(memoria.get("texto")))
        ]

    if not candidatas:
        return {"ok": False, "encontrada": False}

    if len(candidatas) > 1:
        return {
            "ok": False,
            "ambigua": True,
            "candidatas": [
                {"id": memoria.get("id"), "texto": memoria.get("texto")}
                for memoria in candidatas
            ],
        }

    memoria = candidatas[0]
    if not bool(dados.get("confirmado")):
        return {
            "ok": False,
            "precisa_confirmar": True,
            "memoria": {
                "id": memoria.get("id"),
                "texto": memoria.get("texto"),
            },
        }

    apagada = await banco.apagar_memoria(contexto.pessoa_id, memoria["id"])
    return {
        "ok": apagada,
        "esquecida": {
            "id": memoria.get("id"),
            "texto": memoria.get("texto"),
        },
    }


def _parecido(consulta: str, memoria: str) -> bool:
    """Compara um pedido de esquecimento com o texto guardado.

    Aceita flexão ("gosto" × "gosta"), substring e palavras de conteúdo.
    """
    if not consulta or not memoria:
        return False
    if consulta in memoria or memoria in consulta:
        return True
    if SequenceMatcher(None, consulta, memoria).ratio() >= 0.75:
        return True
    return any(
        len(palavra) >= 4 and palavra in memoria
        for palavra in consulta.split()
    )


_VERBO_ESQUECER = re.compile(
    r"\b(?:esque[çc]a|esquece|esque[çc]am|esquecer)\b", re.IGNORECASE
)


_NAO_ESQUECA = re.compile(
    r"\bn[ãa]o\s+(?:se\s+)?esque[çc]a\b", re.IGNORECASE
)


_NAO_LEMBRE = re.compile(r"\bn[ãa]o\s+lembre\s+mais\b", re.IGNORECASE)


_FILLER_ESQUECER = re.compile(
    r"^(?:que\s+eu|que\s+voc[êe]|que|sobre|de|do|da|"
    r"a\s+mem[óo]ria|o\s+fato)\b[\s,:-]*",
    re.IGNORECASE,
)


_GENERICOS_ESQUECER = {
    "isso",
    "disso",
    "essa",
    "esse",
    "essa memoria",
    "esse fato",
}


_AUTORIZACAO_INICIO = re.compile(
    r"^(?:sim|claro|isso|confirmo|confirmado|autorizo|ok|beleza|"
    r"pode\s+(?:guardar|salvar|anotar|registrar))\b",
    re.IGNORECASE,
)


_AUTORIZACAO_MEIO = re.compile(
    r"\bpode\s+(?:guardar|salvar|anotar|registrar)\b", re.IGNORECASE
)


_NEGACAO_CURTA = re.compile(
    r"^(?:sim|claro|isso|ok|beleza)[,\s]+(?:mas\s+)?n[ãa]o\b",
    re.IGNORECASE,
)


_PEDIDO_MEMORIA = re.compile(
    r"^(?:por favor[,\s]+)?(?:lembre|lembra|anota|anote|guarda|guarde|"
    r"registra|registre|memoriza|memorize|n[ãa]o\s+esque[çc]a)\b",
    re.IGNORECASE,
)


_PEDIDO_MEMORIA_MEIO = re.compile(
    r"\b(?:quero|queria|gostaria|preciso)\s+que\s+voc[êe]\s+"
    r"(?:lembre|anote|guarde|registre|memorize)\b",
    re.IGNORECASE,
)


def _autorizacao_explicita(mensagem: str) -> bool:
    """True quando a própria pessoa pediu para lembrar ou deu um sim claro."""
    texto = " ".join(str(mensagem or "").split())
    if not texto or _NEGACAO_CURTA.search(texto):
        return False
    return bool(
        _PEDIDO_MEMORIA.search(texto)
        or _PEDIDO_MEMORIA_MEIO.search(texto)
        or _AUTORIZACAO_INICIO.search(texto)
        or _AUTORIZACAO_MEIO.search(texto)
    )


def consulta_esquecimento(mensagem: str) -> str | None:
    """Extrai o alvo de um pedido explícito de esquecimento.

    "esqueça que eu gosto de jazz" -> "gosto de jazz".
    "não esqueça de comprar leite" não é pedido de esquecimento.
    """
    texto = " ".join(str(mensagem).split())
    if not texto or _NAO_ESQUECA.search(texto):
        return None

    alvo: str | None = None
    nao_lembre = _NAO_LEMBRE.search(texto)
    if nao_lembre is not None:
        alvo = texto[nao_lembre.end() :]
    else:
        verbo = _VERBO_ESQUECER.search(texto)
        if verbo is not None:
            alvo = texto[verbo.end() :]

    if alvo is None:
        return None

    alvo = alvo.strip(" \t\n,.;:!?\"'")
    while True:
        limpo = _FILLER_ESQUECER.sub("", alvo).strip(" \t\n,.;:!?\"'")
        if limpo == alvo:
            break
        alvo = limpo

    if _normalizar_texto(alvo) in _GENERICOS_ESQUECER:
        return None
    return alvo if len(alvo) >= 3 else None
