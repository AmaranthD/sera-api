from __future__ import annotations

import logging
from collections import deque
from time import monotonic
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, StringConstraints

from .rotas import DependenciaConfig, DependenciaUsuario

logger = logging.getLogger(__name__)

router = APIRouter()

_LIMITE = 30
_JANELA = 60.0
_acessos: dict[str, deque[float]] = {}


class TextoEntrada(BaseModel):
    texto: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=1500),
    ]


def _permitir(chave: str) -> bool:
    agora = monotonic()
    fila = _acessos.setdefault(chave, deque())
    while fila and agora - fila[0] > _JANELA:
        fila.popleft()
    if len(fila) >= _LIMITE:
        return False
    fila.append(agora)
    return True


@router.get("/tts")
async def tts_info(config: DependenciaConfig):
    """Informa se a voz neural está disponível, sem gerar áudio."""
    return {"disponivel": config.tts_ativa, "voz": config.tts_voz}


@router.post("/tts")
async def gerar_audio(
    corpo: TextoEntrada,
    request: Request,
    config: DependenciaConfig,
    usuario: DependenciaUsuario,
):
    if not config.tts_ativa:
        raise HTTPException(
            status_code=503,
            detail="a voz neural não está configurada neste servidor",
        )

    chave = usuario.id if usuario else (
        request.client.host if request.client else "anonimo"
    )
    if not _permitir(chave):
        raise HTTPException(
            status_code=429,
            detail="muitos pedidos de áudio; espere um instante",
        )

    try:
        import edge_tts
    except ImportError as erro:  # pragma: no cover - depende do deploy
        raise HTTPException(
            status_code=503, detail="edge-tts não está instalado"
        ) from erro

    comunicador = edge_tts.Communicate(
        corpo.texto,
        config.tts_voz,
        rate=config.tts_rate,
        pitch=config.tts_pitch,
        volume=config.tts_volume,
    )
    audio = bytearray()
    try:
        async for pedaco in comunicador.stream():
            if pedaco.get("type") == "audio":
                audio.extend(pedaco["data"])
    except Exception as erro:
        # O texto não vai para o log: ele pode conter dados pessoais.
        logger.warning("Edge TTS falhou: %s", type(erro).__name__)
        raise HTTPException(
            status_code=502, detail="não foi possível gerar o áudio"
        ) from erro

    if not audio:
        raise HTTPException(
            status_code=502, detail="o serviço de voz não retornou áudio"
        )

    return Response(
        content=bytes(audio),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store"},
    )
