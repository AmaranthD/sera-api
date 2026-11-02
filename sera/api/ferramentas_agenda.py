from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Config
from .ferramentas_base import (
    ContextoFerramentas,
    FerramentaInvalida,
    NOME_AGENDAR,
    NOME_CANCELAR_COMPROMISSO,
    NOME_CONSULTAR_AGENDA,
    _DURACAO_PADRAO_MINUTOS,
    _JANELA_PADRAO_DIAS,
    _MAX_AGENDA,
    _MAX_LEMBRETE_MINUTOS,
    _TAMANHO_MAXIMO_TITULO_AGENDA,
    _normalizar_texto,
)
from .tempo import agora as _agora_local
from .tempo import formatar_momento as _formatar_momento
from .tempo import iso_utc as _iso_utc

_TITULOS_GENERICOS = {
    "exemplo",
    "por exemplo",
    "teste",
    "compromisso",
    "agendamento",
    "compromisso de exemplo",
    "agendamento de exemplo",
    "novo compromisso",
    "novo agendamento",
    "sem titulo",
}


ESQUEMA_AGENDAR = {
    "type": "function",
    "function": {
        "name": NOME_AGENDAR,
        "description": (
            "Cria um compromisso na agenda da pessoa, com lembrete por "
            "notificação. Use quando ela pedir para agendar, marcar, "
            "reservar ou anotar um compromisso em uma data e hora. Converta "
            "expressões relativas ('amanhã', 'sexta') em datas absolutas "
            "usando o bloco AGORA do sistema."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "titulo": {
                    "type": "string",
                    "description": "Título curto do compromisso.",
                },
                "inicio": {
                    "type": "string",
                    "description": (
                        "Início no formato AAAA-MM-DDTHH:MM, sem fuso; o "
                        "fuso da pessoa é aplicado automaticamente."
                    ),
                },
                "fim": {
                    "type": "string",
                    "description": (
                        "Fim no mesmo formato. Se não souber, omita: o "
                        "padrão é 1 hora depois do início."
                    ),
                },
                "descricao": {
                    "type": "string",
                    "description": "Detalhes opcionais do compromisso.",
                },
                "lembrete_minutos": {
                    "type": "integer",
                    "description": (
                        "Quantos minutos antes avisar (0 a 10080). "
                        "Padrão: 10."
                    ),
                },
            },
            "required": ["titulo", "inicio"],
        },
    },
}


ESQUEMA_CONSULTAR_AGENDA = {
    "type": "function",
    "function": {
        "name": NOME_CONSULTAR_AGENDA,
        "description": (
            "Lista os compromissos da agenda da pessoa em um período. Use "
            "quando ela perguntar o que tem marcado, se está livre em uma "
            "data ou pedir a agenda. Sem período, mostra os próximos 30 dias."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "de": {
                    "type": "string",
                    "description": (
                        "Início do período em AAAA-MM-DD ou "
                        "AAAA-MM-DDTHH:MM. Omita para começar agora."
                    ),
                },
                "ate": {
                    "type": "string",
                    "description": (
                        "Fim do período no mesmo formato. Omita para 30 "
                        "dias à frente."
                    ),
                },
            },
        },
    },
}


ESQUEMA_CANCELAR_COMPROMISSO = {
    "type": "function",
    "function": {
        "name": NOME_CANCELAR_COMPROMISSO,
        "description": (
            "Cancela (apaga) um compromisso da agenda. Use só quando a "
            "pessoa pedir explicitamente para cancelar, desmarcar ou "
            "remover um compromisso. Informe o id (obtido em "
            "consultar_agenda) ou o título."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Id do compromisso, se você já o tiver.",
                },
                "titulo": {
                    "type": "string",
                    "description": (
                        "Trecho do título, quando não souber o id. Se houver "
                        "mais de um parecido, a ferramenta devolve as opções."
                    ),
                },
            },
        },
    },
}


INSTRUCAO_AGENDA = """\
## Agenda

Você pode marcar, consultar e cancelar compromissos na agenda da pessoa.

- Antes de `agendar`, sempre tenha um título/assunto dito pela pessoa.
  Se ela só deu dia e hora, pergunte: "qual é o assunto do compromisso?".
  Nunca invente nem use "por exemplo", "teste", "compromisso" ou
  "agendamento" como título.
- Use `agendar` quando ela pedir para marcar, agendar, reservar ou anotar
  um compromisso com data e hora. Informe `titulo` e `inicio` no formato
  `AAAA-MM-DDTHH:MM`; `fim` é opcional (uma hora depois por padrão).
- Use `consultar_agenda` quando ela perguntar o que tem marcado ou se está
  livre. Sem período, a ferramenta mostra os próximos 30 dias.
- Use `cancelar_compromisso` só quando ela pedir explicitamente para
  cancelar, desmarcar ou remover um compromisso. Se não souber o id, passe
  um trecho do `titulo`.
- Chame `agendar` uma única vez por compromisso. Não repita a chamada com
  os mesmos dados: a primeira já marca, e a segunda só encontraria o
  compromisso recém-criado.
- Converta datas relativas ("hoje", "amanhã", "sexta") em datas absolutas
  usando o bloco AGORA. Se faltar a hora ou o dia, pergunte antes de
  agendar. Não invente data nem duração.
- Se a ferramenta avisar que o horário cruza outro compromisso, não force:
  mostre o conflito e pergunte outro horário.
- Depois de agendar ou cancelar, confirme em uma frase curta, com o dia, a
  hora e o aviso (minutos antes). Não diga que não consegue avisar em datas
  futuras: o lembrete da agenda cuida disso.
"""


def _contexto_agenda(
    contexto: ContextoFerramentas,
) -> tuple[Any, str, Config]:
    if (
        contexto.banco is None
        or not contexto.pessoa_id
        or contexto.config is None
    ):
        raise FerramentaInvalida("a agenda não está disponível nesta conversa")
    return contexto.banco, contexto.pessoa_id, contexto.config


def _data_da_agenda(valor: Any, config: Config) -> datetime:
    texto = str(valor or "").strip()
    if not texto:
        raise FerramentaInvalida(
            "informe a data e a hora no formato AAAA-MM-DDTHH:MM"
        )
    if texto.endswith("Z"):
        texto = f"{texto[:-1]}+00:00"
    try:
        momento = datetime.fromisoformat(texto)
    except ValueError as erro:
        raise FerramentaInvalida(
            f"data inválida: {valor!r}; use AAAA-MM-DD ou AAAA-MM-DDTHH:MM"
        ) from erro
    if momento.tzinfo is None:
        try:
            momento = momento.replace(tzinfo=ZoneInfo(config.fuso_horario))
        except (ValueError, ZoneInfoNotFoundError) as erro:
            raise FerramentaInvalida(
                f"fuso horário inválido: {config.fuso_horario}"
            ) from erro
    return momento


def _somente_data(valor: str) -> bool:
    return re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor.strip()) is not None


def _compromisso_publico(linha: Mapping, fuso_exibicao: str) -> dict:
    fuso = str(linha.get("fuso") or fuso_exibicao)
    try:
        ZoneInfo(fuso)
    except (ValueError, ZoneInfoNotFoundError):
        fuso = fuso_exibicao
    return {
        "id": linha.get("id"),
        "titulo": linha.get("titulo"),
        "descricao": linha.get("descricao") or "",
        "inicio": _formatar_momento(linha.get("inicio"), fuso),
        "fim": _formatar_momento(linha.get("fim"), fuso),
        "fuso": fuso,
    }


async def _agendar(
    dados: Mapping, contexto: ContextoFerramentas
) -> dict:
    banco, pessoa, config = _contexto_agenda(contexto)

    titulo = " ".join(str(dados.get("titulo") or "").split())
    titulo = titulo[:_TAMANHO_MAXIMO_TITULO_AGENDA].rstrip()
    if not titulo or _normalizar_texto(titulo) in _TITULOS_GENERICOS:
        return {"ok": False, "precisa_titulo": True}

    inicio = _data_da_agenda(dados.get("inicio"), config)
    fim_bruto = str(dados.get("fim") or "").strip()
    fim = (
        _data_da_agenda(fim_bruto, config)
        if fim_bruto
        else inicio + timedelta(minutes=_DURACAO_PADRAO_MINUTOS)
    )
    if fim <= inicio:
        raise FerramentaInvalida("o fim precisa ser depois do início")

    lembrete = dados.get("lembrete_minutos")
    try:
        minutos = int(lembrete) if lembrete is not None else 10
    except (TypeError, ValueError) as erro:
        raise FerramentaInvalida(
            "lembrete_minutos precisa ser um número inteiro"
        ) from erro
    minutos = max(0, min(minutos, _MAX_LEMBRETE_MINUTOS))

    inicio_iso = _iso_utc(inicio)
    fim_iso = _iso_utc(fim)
    conflito = await banco.conflito_compromisso(
        pessoa, inicio_iso, fim_iso
    )
    if conflito is not None:
        return {
            "ok": False,
            "conflito": _compromisso_publico(
                conflito, config.fuso_horario
            ),
        }

    criado = await banco.criar_compromisso(
        pessoa,
        {
            "titulo": titulo,
            "descricao": " ".join(
                str(dados.get("descricao") or "").split()
            )[:2000],
            "inicio": inicio_iso,
            "fim": fim_iso,
            "fuso": config.fuso_horario,
            "lembrete_minutos": minutos,
            "lembrete_em": _iso_utc(
                inicio - timedelta(minutes=minutos)
            ),
        },
    )
    return {
        "ok": True,
        "compromisso": _compromisso_publico(
            criado, config.fuso_horario
        ),
    }


async def _consultar_agenda(
    dados: Mapping, contexto: ContextoFerramentas
) -> dict:
    banco, pessoa, config = _contexto_agenda(contexto)

    de_bruto = str(dados.get("de") or "").strip()
    ate_bruto = str(dados.get("ate") or "").strip()

    de = (
        _data_da_agenda(de_bruto, config)
        if de_bruto
        else _agora_local(config)
    )
    if ate_bruto:
        ate = _data_da_agenda(ate_bruto, config)
        if _somente_data(ate_bruto):
            ate += timedelta(days=1)
    else:
        ate = de + timedelta(days=_JANELA_PADRAO_DIAS)
    if ate <= de:
        raise FerramentaInvalida(
            "o fim do período precisa ser depois do início"
        )

    linhas = await banco.listar_compromissos(
        pessoa, _iso_utc(de), _iso_utc(ate)
    )
    return {
        "ok": True,
        "de": _formatar_momento(de, config.fuso_horario),
        "ate": _formatar_momento(ate, config.fuso_horario),
        "compromissos": [
            _compromisso_publico(linha, config.fuso_horario)
            for linha in linhas[:_MAX_AGENDA]
        ],
    }


async def _cancelar_compromisso(
    dados: Mapping, contexto: ContextoFerramentas
) -> dict:
    banco, pessoa, config = _contexto_agenda(contexto)

    identificador = str(dados.get("id") or "").strip()
    titulo = " ".join(str(dados.get("titulo") or "").split())

    if identificador:
        linha = await banco.obter_compromisso(identificador)
        if linha is None or linha.get("pessoa_id") != pessoa:
            return {"ok": False, "encontrado": False}
    elif titulo:
        chave = _normalizar_texto(titulo)
        linhas = await banco.listar_compromissos(pessoa, None, None)
        candidatas = [
            item
            for item in linhas
            if chave
            and (
                chave in _normalizar_texto(item.get("titulo"))
                or _normalizar_texto(item.get("titulo")) in chave
            )
        ]
        if not candidatas:
            return {"ok": False, "encontrado": False}
        if len(candidatas) > 1:
            return {
                "ok": False,
                "ambigua": True,
                "candidatas": [
                    _compromisso_publico(item, config.fuso_horario)
                    for item in candidatas[:_MAX_AGENDA]
                ],
            }
        linha = candidatas[0]
    else:
        raise FerramentaInvalida("informe o id ou o título do compromisso")

    if not await banco.apagar_compromisso(linha["id"]):
        return {"ok": False, "encontrado": False}
    return {
        "ok": True,
        "cancelado": _compromisso_publico(
            linha, config.fuso_horario
        ),
    }
