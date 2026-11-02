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
    except ValueError as erro:
        # py_vapid só entende a chave privada em base64url (32 bytes) ou
        # DER. PEM colado no painel com quebras literais cai aqui.
        raise NotificacoesIndisponiveis(
            "VAPID_PRIVATE_KEY inválida: use a chave privada em base64url "
            "(32 bytes) ou DER"
        ) from erro
    except Exception as erro:
        raise FalhaPush(str(erro)) from erro


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


def payload_mensagem(
    conversa_id: str,
    resposta_id: str,
    texto: str,
    *,
    erro: bool = False,
    preview: bool = False,
) -> dict:
    """Notificação de uma resposta do chat assíncrono pronta.

    O conteúdo só aparece na notificação se `preview` estiver ligado; por
    padrão a tela de bloqueio mostra apenas que a resposta chegou.
    """
    trecho = " ".join(str(texto or "").split())
    if erro:
        corpo = "A Sera não conseguiu concluir a resposta. Abra para tentar."
    elif not preview or not trecho:
        corpo = "Sua resposta está pronta."
    else:
        limite = 140
        corpo = trecho[:limite].rstrip()
        if len(trecho) > limite:
            corpo = f"{corpo}…"
    return {
        "titulo": "Sera",
        "corpo": corpo,
        "url": f"/c/{conversa_id}",
        "tag": f"chat-{resposta_id}",
        "tipo": "mensagem",
        "conversa_id": conversa_id,
        "resposta_id": resposta_id,
    }


def validar_chaves(config: Config) -> None:
    """Confere o formato das chaves VAPID antes de tentar enviar."""
    import base64

    publica = config.vapid_public_key or ""
    privada = config.vapid_private_key or ""
    try:
        bruta = base64.urlsafe_b64decode(
            publica + "=" * (-len(publica) % 4)
        )
    except Exception as erro:
        raise ValueError("VAPID_PUBLIC_KEY não é base64url válida") from erro
    if len(bruta) != 65 or bruta[0] != 4:
        raise ValueError(
            "VAPID_PUBLIC_KEY inválida: espere 65 bytes começando em 0x04"
        )

    try:
        chave = base64.urlsafe_b64decode(
            privada + "=" * (-len(privada) % 4)
        )
    except Exception as erro:
        raise ValueError("VAPID_PRIVATE_KEY não é base64url válida") from erro
    if len(chave) == 32:
        return
    try:
        from cryptography.hazmat.primitives import serialization

        serialization.load_der_private_key(chave, password=None)
    except Exception as erro:
        raise ValueError(
            "VAPID_PRIVATE_KEY inválida: espere 32 bytes em base64url ou DER"
        ) from erro
