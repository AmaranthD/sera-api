from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Mapping

import anyio

from .config import Config

logger = logging.getLogger(__name__)


class NotificacoesIndisponiveis(Exception):
    """Falta a dependência de Web Push ou as chaves VAPID."""


class FalhaPush(Exception):
    def __init__(self, detalhe: str, *, status: int | None = None) -> None:
        super().__init__(detalhe)
        self.detalhe = detalhe
        self.status = status

    @property
    def inscricao_morta(self) -> bool:
        # 404 e 410 significam que o navegador descartou a inscrição.
        return self.status in (404, 410)


def _enviar_sincrono(
    inscricao: Mapping[str, Any],
    payload: dict,
    config: Config,
) -> None:
    try:
        from pywebpush import WebPushException, webpush
    except ImportError as erro:  # pragma: no cover - só sem dependência
        raise NotificacoesIndisponiveis(
            "pywebpush não está instalado"
        ) from erro

    if not config.vapid_private_key:
        raise NotificacoesIndisponiveis("VAPID_PRIVATE_KEY não configurada")

    assinatura = {
        "endpoint": inscricao["endpoint"],
        "keys": {
            "p256dh": inscricao["p256dh"],
            "auth": inscricao["auth"],
        },
    }
    try:
        webpush(
            subscription_info=assinatura,
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=config.vapid_private_key,
            vapid_claims={"sub": config.vapid_subject},
            timeout=10,
        )
    except WebPushException as erro:
        resposta = getattr(erro, "response", None)
        status = getattr(resposta, "status_code", None)
        raise FalhaPush(str(erro), status=status) from erro


async def enviar_push(
    inscricao: Mapping[str, Any],
    payload: dict,
    config: Config,
) -> None:
    """Envia uma notificação Web Push sem bloquear o loop."""
    await anyio.to_thread.run_sync(
        _enviar_sincrono, inscricao, payload, config
    )


def payload_lembrete(compromisso: Mapping[str, Any]) -> dict:
    corpo = compromisso.get("titulo") or "Você tem um compromisso"
    try:
        from zoneinfo import ZoneInfo

        fuso = ZoneInfo(compromisso.get("fuso") or "UTC")
        inicio = datetime.fromisoformat(compromisso["inicio"])
        corpo = f"{corpo} — {inicio.astimezone(fuso):%d/%m às %H:%M}"
    except (ValueError, KeyError):
        pass
    return {
        "titulo": "Compromisso chegando",
        "corpo": corpo,
        "url": "/agenda",
        "tag": f"compromisso-{compromisso['id']}",
        "compromisso_id": compromisso["id"],
    }
