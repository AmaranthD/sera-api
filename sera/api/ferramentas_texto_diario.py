from __future__ import annotations

import re
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Config
from .ferramentas_base import (
    ContextoFerramentas,
    FerramentaInvalida,
    NOME_TEXTO_DIARIO,
)
from .texto_diario import TextoDiarioIndisponivel, entregar_texto_do_dia

_HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_ACOES = ("ativar", "desativar", "alterar_horario", "consultar", "enviar_agora")


ESQUEMA_TEXTO_DIARIO = {
    "type": "function",
    "function": {
        "name": NOME_TEXTO_DIARIO,
        "description": (
            "Configura o envio diário do texto diário das Testemunhas de "
            "Jeová. Use quando a pessoa pedir para receber o texto diário "
            "todo dia em um horário, mudar o horário, desativar, consultar "
            "a configuração ou enviar agora. A entrega é determinística: "
            "vai para uma conversa chamada 'Texto diário' e gera uma "
            "notificação no dispositivo."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "acao": {
                    "type": "string",
                    "enum": list(_ACOES),
                    "description": (
                        "ativar: liga o envio diário; desativar: desliga; "
                        "alterar_horario: mantém ligado e muda a hora; "
                        "consultar: mostra a configuração atual; "
                        "enviar_agora: entrega o texto de hoje na hora."
                    ),
                },
                "hora": {
                    "type": "string",
                    "description": (
                        "Horário local no formato HH:MM, de 00:00 a 23:59. "
                        "Obrigatório em alterar_horario. Se a pessoa não "
                        "disser a hora em ativar, omita e o padrão é 07:00."
                    ),
                },
                "fuso": {
                    "type": "string",
                    "description": (
                        "Fuso IANA opcional (ex.: America/Sao_Paulo). Omita "
                        "para usar o fuso padrão da conta."
                    ),
                },
            },
            "required": ["acao"],
        },
    },
}


INSTRUCAO_TEXTO_DIARIO = """\
## Texto diário

Você pode configurar o envio diário do texto diário do JW para a pessoa.

- Use `texto_diario` quando ela pedir para receber o texto diário todo dia,
  em um horário, para mudar o horário, desligar ou ver como está.
- `ativar` exige uma hora (HH:MM). Se ela disser "todo dia às 7", use
  `hora=07:00`. Se ela não disser a hora, pergunte antes de ativar; não
  invente um horário.
- `alterar_horario` muda a hora mantendo o envio ligado. `desativar`
  desliga sem apagar a conversa e o histórico.
- A entrega vai para uma conversa separada chamada "Texto diário", com os
  links do JW que abrem em um modal. Não repita o texto diário na resposta:
  só confirme em uma frase curta.
- `enviar_agora` entrega o texto de hoje imediatamente e pode ser usado como
  teste. Se o texto ainda não estiver publicado, avise que tente mais tarde.
- Se a pessoa pedir para mudar o fuso, informe o fuso IANA; caso contrário,
  use o padrão da conta.
"""


def _contexto_texto_diario(
    contexto: ContextoFerramentas,
) -> tuple[Any, str, Config]:
    if (
        contexto.banco is None
        or not contexto.pessoa_id
        or contexto.config is None
    ):
        raise FerramentaInvalida(
            "o texto diário não está disponível nesta conversa"
        )
    return contexto.banco, contexto.pessoa_id, contexto.config


def _validar_hora(valor: Any) -> str:
    hora = str(valor or "").strip()
    if not _HORA.match(hora):
        raise FerramentaInvalida(
            "informe o horário no formato HH:MM, de 00:00 a 23:59"
        )
    return hora


def _validar_fuso(valor: Any, padrao: str) -> str:
    fuso = str(valor or "").strip() or padrao
    try:
        ZoneInfo(fuso)
    except (ValueError, ZoneInfoNotFoundError) as erro:
        raise FerramentaInvalida(f"fuso horário inválido: {fuso}") from erro
    return fuso


async def _texto_diario(
    dados: Mapping, contexto: ContextoFerramentas
) -> dict:
    banco, pessoa_id, config = _contexto_texto_diario(contexto)
    acao = str(dados.get("acao") or "").strip()
    if acao not in _ACOES:
        raise FerramentaInvalida(
            "acao precisa ser ativar, desativar, alterar_horario, "
            "consultar ou enviar_agora"
        )

    existente = await banco.obter_assinatura_texto_diario(pessoa_id) or {}

    if acao == "consultar":
        return {
            "ok": True,
            "assinatura": {
                "ativo": bool(existente.get("ativo")),
                "hora": existente.get("hora") or "07:00",
                "fuso": existente.get("fuso") or config.fuso_horario,
                "ultimo_envio_dia": existente.get("ultimo_envio_dia"),
            },
        }

    if acao == "enviar_agora":
        try:
            entrega = await entregar_texto_do_dia(
                banco,
                config,
                pessoa_id,
                conversa_id=existente.get("conversa_id"),
                fuso=existente.get("fuso") or config.fuso_horario,
            )
        except TextoDiarioIndisponivel as erro:
            raise FerramentaInvalida(
                f"o texto diário ainda não está disponível: {erro}"
            ) from erro
        return {"ok": True, "entrega": entrega}

    hora_existente = existente.get("hora") or "07:00"
    fuso = _validar_fuso(
        dados.get("fuso"),
        str(existente.get("fuso") or config.fuso_horario),
    )

    if acao == "desativar":
        salva = await banco.salvar_assinatura_texto_diario(
            pessoa_id, False, hora_existente, fuso
        )
        return {"ok": True, "assinatura": salva}

    if acao == "alterar_horario":
        if not str(dados.get("hora") or "").strip():
            raise FerramentaInvalida(
                "para alterar o horário, informe a nova hora em HH:MM"
            )
        hora = _validar_hora(dados.get("hora"))
    else:
        pedida = str(dados.get("hora") or "").strip()
        hora = _validar_hora(pedida) if pedida else hora_existente

    salva = await banco.salvar_assinatura_texto_diario(
        pessoa_id, True, hora, fuso
    )
    return {"ok": True, "assinatura": salva}
