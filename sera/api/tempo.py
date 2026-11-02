from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def agora(fuso: str) -> datetime:
    """Data/hora atual no fuso pedido."""
    return datetime.now(ZoneInfo(fuso))


def agora_iso() -> str:
    """Data/hora atual em UTC, no formato gravado pelo banco."""
    return iso_utc(datetime.now(timezone.utc))


def com_fuso(valor: datetime, fuso: str) -> datetime:
    """Aplica o fuso padrão quando a data chega sem tzinfo."""
    if valor.tzinfo is not None:
        return valor
    return valor.replace(tzinfo=ZoneInfo(fuso))


def iso_utc(valor: datetime) -> str:
    """Formato usado no banco para todas as datas em UTC."""
    return valor.astimezone(timezone.utc).isoformat(timespec="microseconds")


def formatar_momento(valor: Any, fuso: str) -> str:
    """Data guardada em UTC -> 'dd/mm/aaaa hh:mm' no fuso de exibição."""
    try:
        momento = datetime.fromisoformat(str(valor))
    except (TypeError, ValueError):
        return str(valor or "")
    try:
        zona = ZoneInfo(fuso)
    except (ValueError, ZoneInfoNotFoundError):
        zona = timezone.utc
    return momento.astimezone(zona).strftime("%d/%m/%Y %H:%M")
