from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, FastAPI, Header, HTTPException, Query, Request, Response

from .config import Config
from .rotas import (
    DependenciaBanco,
    DependenciaConfig,
    DependenciaUsuario,
    _pessoa_do_usuario,
)
from .schemas import (
    CompromissoAtualizacao,
    CompromissoEntrada,
    InscricaoPushEntrada,
)
from .tempo import com_fuso as _com_fuso
from .tempo import iso_utc as _utc
from .webpush import (
    FalhaPush,
    NotificacoesIndisponiveis,
    enviar_push,
    payload_lembrete,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_PAYLOAD_TESTE = {
    "titulo": "Sera",
    "corpo": "As notificações de compromissos estão ativas.",
    "url": "/agenda",
    "tag": "teste",
}


def _normalizar(
    *,
    titulo: str,
    descricao: str | None,
    inicio: datetime,
    fim: datetime,
    fuso: str | None,
    lembrete_minutos: int,
    config: Config,
) -> dict:
    if fim <= inicio:
        raise HTTPException(
            status_code=422, detail="o fim precisa ser depois do início"
        )
    nome_fuso = fuso or config.fuso_horario
    try:
        ZoneInfo(nome_fuso)
    except (ValueError, ZoneInfoNotFoundError) as erro:
        raise HTTPException(
            status_code=422, detail=f"fuso horário inválido: {nome_fuso}"
        ) from erro
    return {
        "titulo": titulo,
        "descricao": descricao or "",
        "inicio": _utc(inicio),
        "fim": _utc(fim),
        "fuso": nome_fuso,
        "lembrete_minutos": lembrete_minutos,
        "lembrete_em": _utc(inicio - timedelta(minutes=lembrete_minutos)),
    }


async def _compromisso_da_pessoa(
    compromisso_id: str, pessoa_id: str, banco
) -> dict:
    compromisso = await banco.obter_compromisso(compromisso_id)
    if compromisso is None or compromisso["pessoa_id"] != pessoa_id:
        raise HTTPException(
            status_code=404, detail="compromisso não encontrado"
        )
    return compromisso


@router.get("/pessoas/{pessoa_id}/compromissos")
async def listar_compromissos(
    pessoa_id: str,
    banco: DependenciaBanco,
    config: DependenciaConfig,
    usuario: DependenciaUsuario,
    de: datetime | None = Query(default=None),
    ate: datetime | None = Query(default=None),
):
    pessoa = _pessoa_do_usuario(usuario, pessoa_id)
    return await banco.listar_compromissos(
        pessoa,
        _utc(_com_fuso(de, config.fuso_horario)) if de is not None else None,
        _utc(_com_fuso(ate, config.fuso_horario)) if ate is not None else None,
    )


@router.post("/pessoas/{pessoa_id}/compromissos", status_code=201)
async def criar_compromisso(
    pessoa_id: str,
    corpo: CompromissoEntrada,
    banco: DependenciaBanco,
    config: DependenciaConfig,
    usuario: DependenciaUsuario,
):
    pessoa = _pessoa_do_usuario(usuario, pessoa_id)
    dados = _normalizar(
        titulo=corpo.titulo,
        descricao=corpo.descricao,
        inicio=_com_fuso(corpo.inicio, config.fuso_horario),
        fim=_com_fuso(corpo.fim, config.fuso_horario),
        fuso=corpo.fuso,
        lembrete_minutos=corpo.lembrete_minutos,
        config=config,
    )
    conflito = await banco.conflito_compromisso(
        pessoa, dados["inicio"], dados["fim"]
    )
    if conflito is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Esse horário cruza com “{conflito['titulo']}”. "
                "Escolha outro horário."
            ),
        )
    return await banco.criar_compromisso(pessoa, dados)


@router.patch("/pessoas/{pessoa_id}/compromissos/{compromisso_id}")
async def atualizar_compromisso(
    pessoa_id: str,
    compromisso_id: str,
    corpo: CompromissoAtualizacao,
    banco: DependenciaBanco,
    config: DependenciaConfig,
    usuario: DependenciaUsuario,
):
    pessoa = _pessoa_do_usuario(usuario, pessoa_id)
    atual = await _compromisso_da_pessoa(compromisso_id, pessoa, banco)

    inicio = (
        _com_fuso(corpo.inicio, config.fuso_horario)
        if corpo.inicio is not None
        else datetime.fromisoformat(atual["inicio"])
    )
    fim = (
        _com_fuso(corpo.fim, config.fuso_horario)
        if corpo.fim is not None
        else datetime.fromisoformat(atual["fim"])
    )
    dados = _normalizar(
        titulo=corpo.titulo if corpo.titulo is not None else atual["titulo"],
        descricao=(
            corpo.descricao
            if corpo.descricao is not None
            else atual["descricao"]
        ),
        inicio=inicio,
        fim=fim,
        fuso=corpo.fuso if corpo.fuso is not None else atual["fuso"],
        lembrete_minutos=(
            corpo.lembrete_minutos
            if corpo.lembrete_minutos is not None
            else atual["lembrete_minutos"]
        ),
        config=config,
    )
    conflito = await banco.conflito_compromisso(
        pessoa, dados["inicio"], dados["fim"], excluir_id=compromisso_id
    )
    if conflito is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Esse horário cruza com “{conflito['titulo']}”. "
                "Escolha outro horário."
            ),
        )
    atualizado = await banco.atualizar_compromisso(compromisso_id, dados)
    if atualizado is None:
        raise HTTPException(
            status_code=404, detail="compromisso não encontrado"
        )
    return atualizado


@router.delete(
    "/pessoas/{pessoa_id}/compromissos/{compromisso_id}",
    status_code=204,
)
async def apagar_compromisso(
    pessoa_id: str,
    compromisso_id: str,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    pessoa = _pessoa_do_usuario(usuario, pessoa_id)
    await _compromisso_da_pessoa(compromisso_id, pessoa, banco)
    await banco.apagar_compromisso(compromisso_id)
    return Response(status_code=204)


@router.get("/notificacoes/chave")
async def chave_notificacoes(config: DependenciaConfig):
    if not config.notificacoes_ativas:
        raise HTTPException(
            status_code=503,
            detail="as notificações não estão configuradas neste servidor",
        )
    return {"chave": config.vapid_public_key}


@router.get("/pessoas/{pessoa_id}/notificacoes/inscricoes")
async def listar_inscricoes(
    pessoa_id: str,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    pessoa = _pessoa_do_usuario(usuario, pessoa_id)
    inscricoes = await banco.listar_inscricoes(pessoa)
    return [
        {
            "id": inscricao["id"],
            "endpoint": inscricao["endpoint"],
            "criada_em": inscricao.get("criada_em"),
        }
        for inscricao in inscricoes
    ]


@router.post(
    "/pessoas/{pessoa_id}/notificacoes/inscricoes", status_code=201
)
async def criar_inscricao(
    pessoa_id: str,
    corpo: InscricaoPushEntrada,
    banco: DependenciaBanco,
    config: DependenciaConfig,
    usuario: DependenciaUsuario,
):
    pessoa = _pessoa_do_usuario(usuario, pessoa_id)
    if not config.notificacoes_ativas:
        raise HTTPException(
            status_code=503,
            detail="as notificações não estão configuradas neste servidor",
        )
    inscricao = await banco.criar_inscricao(
        pessoa,
        corpo.endpoint,
        corpo.keys.p256dh,
        corpo.keys.auth,
        corpo.user_agent,
    )
    return {
        "id": inscricao["id"],
        "endpoint": inscricao["endpoint"],
        "criada_em": inscricao.get("criada_em"),
    }


@router.delete("/pessoas/{pessoa_id}/notificacoes/inscricoes", status_code=204)
async def remover_inscricao(
    pessoa_id: str,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
    endpoint: str = Query(min_length=8),
):
    pessoa = _pessoa_do_usuario(usuario, pessoa_id)
    inscricoes = await banco.listar_inscricoes(pessoa)
    if not any(item["endpoint"] == endpoint for item in inscricoes):
        raise HTTPException(
            status_code=404, detail="inscrição não encontrada"
        )
    await banco.apagar_inscricao_por_endpoint(endpoint)
    return Response(status_code=204)


@router.post("/pessoas/{pessoa_id}/notificacoes/teste")
async def testar_notificacao(
    pessoa_id: str,
    banco: DependenciaBanco,
    config: DependenciaConfig,
    usuario: DependenciaUsuario,
):
    pessoa = _pessoa_do_usuario(usuario, pessoa_id)
    if not config.notificacoes_ativas:
        raise HTTPException(
            status_code=503,
            detail="as notificações não estão configuradas neste servidor",
        )
    inscricoes = await banco.listar_inscricoes(pessoa)
    if not inscricoes:
        raise HTTPException(
            status_code=404, detail="nenhum dispositivo inscrito"
        )
    enviados = 0
    for inscricao in inscricoes:
        try:
            await enviar_push(inscricao, _PAYLOAD_TESTE, config)
            enviados += 1
        except FalhaPush as erro:
            if erro.inscricao_morta:
                await banco.apagar_inscricao_por_endpoint(
                    inscricao["endpoint"]
                )
        except NotificacoesIndisponiveis as erro:
            raise HTTPException(
                status_code=503, detail=str(erro)
            ) from erro
    return {"enviados": enviados, "dispositivos": len(inscricoes)}


async def disparar_lembretes(
    banco, config: Config, momento: datetime | None = None
) -> dict:
    instante = momento or datetime.now(timezone.utc)
    iso = _utc(instante)
    pendentes = await banco.lembretes_pendentes(iso)
    enviados = 0
    falhas = 0
    for compromisso in pendentes:
        # Reivindica antes de enviar: com várias instâncias, só uma dispara.
        if not await banco.reivindicar_lembrete(compromisso["id"], iso):
            continue
        inscricoes = await banco.listar_inscricoes(compromisso["pessoa_id"])
        payload = payload_lembrete(compromisso)
        for inscricao in inscricoes:
            try:
                await enviar_push(inscricao, payload, config)
                enviados += 1
            except FalhaPush as erro:
                falhas += 1
                if erro.inscricao_morta:
                    await banco.apagar_inscricao_por_endpoint(
                        inscricao["endpoint"]
                    )
            except NotificacoesIndisponiveis as erro:
                logger.warning("push indisponível: %s", erro)
                return {
                    "pendentes": len(pendentes),
                    "enviados": enviados,
                    "falhas": falhas,
                }
    return {
        "pendentes": len(pendentes),
        "enviados": enviados,
        "falhas": falhas,
    }


@router.post("/notificacoes/disparar")
async def disparar(
    request: Request,
    config: DependenciaConfig,
    segredo: Annotated[str | None, Header(alias="X-Sera-Segredo")] = None,
):
    if not config.notificacoes_segredo:
        raise HTTPException(
            status_code=503,
            detail="NOTIFICACOES_SEGREDO não configurado",
        )
    if not segredo or not secrets.compare_digest(
        segredo, config.notificacoes_segredo
    ):
        raise HTTPException(status_code=401, detail="segredo inválido")
    banco = getattr(request.app.state, "banco_admin", None)
    if banco is None:
        raise HTTPException(
            status_code=503, detail="banco de notificações indisponível"
        )
    if not config.notificacoes_ativas:
        raise HTTPException(
            status_code=503, detail="notificações não configuradas"
        )
    return await disparar_lembretes(banco, config)


async def laco_lembretes(app: FastAPI, config: Config) -> None:
    """Dispara lembretes periodicamente enquanto a API estiver acordada.

    O cron externo (`/notificacoes/disparar`) cobre o caso do Render dormir.
    """
    while True:
        try:
            banco = getattr(app.state, "banco_admin", None)
            if banco is not None:
                await disparar_lembretes(banco, config)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("falha ao disparar lembretes")
        await asyncio.sleep(config.notificacoes_intervalo)
