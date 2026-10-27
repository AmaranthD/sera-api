from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from datetime import datetime
from typing import Annotated

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from ..prompt import (
    AjusteAprendido,
    AjusteInvalido,
    CategoriaFato,
    FaixaEtaria,
    Fato,
    MemoriaDaPessoa,
    OrigemAjuste,
    Perfil,
    Pessoa,
    Personality,
    TipoAjuste,
    Trecho,
    contem_segredo,
    montar,
    validar_ajustes,
)
from .auth import Usuario, usuario_atual
from .config import Config
from .db import Banco
from .db_supabase import Conflito
from .llm import ClienteLLM, Delta, ErroDoProvedor, Fim, Uso
from .schemas import (
    AjusteEntrada,
    ChatEntrada,
    MemoriaEntrada,
    PessoaEntrada,
    TemaEntrada,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def config_da_app(request: Request) -> Config:
    return request.app.state.config


DependenciaUsuario = Annotated[Usuario | None, Depends(usuario_atual)]


async def banco_da_app(
    request: Request, usuario: DependenciaUsuario
) -> Banco:
    fabrica = getattr(request.app.state, "banco_fabrica", None)
    if fabrica is None:
        yield request.app.state.banco
        return

    banco = fabrica(usuario.token if usuario else None)
    try:
        yield banco
    finally:
        fechar = getattr(banco, "fechar", None)
        if fechar is not None:
            await fechar()


def llm_da_app(request: Request) -> ClienteLLM:
    return request.app.state.llm


def personality_da_app(request: Request) -> Personality:
    return request.app.state.personality


DependenciaConfig = Annotated[Config, Depends(config_da_app)]
DependenciaBanco = Annotated[Banco, Depends(banco_da_app)]
DependenciaLLM = Annotated[ClienteLLM, Depends(llm_da_app)]
DependenciaPersonality = Annotated[Personality, Depends(personality_da_app)]


def _pessoa_do_usuario(
    usuario: Usuario | None, solicitado: str | None
) -> str:
    if usuario is not None:
        if solicitado is not None and solicitado != usuario.id:
            raise HTTPException(status_code=403, detail="acesso negado")
        return usuario.id
    if not solicitado:
        raise HTTPException(
            status_code=401, detail="pessoa não identificada"
        )
    return solicitado


@router.post("/pessoas", status_code=201)
async def criar_pessoa(
    corpo: PessoaEntrada,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    pessoa_id = _pessoa_do_usuario(usuario, corpo.id)
    if await banco.obter_pessoa(pessoa_id) is not None:
        raise HTTPException(status_code=409, detail="pessoa já existe")
    acesso_vault = (
        corpo.acesso_vault
        if corpo.acesso_vault is not None
        else corpo.faixa_etaria is FaixaEtaria.ADULTO
    )
    try:
        return await banco.criar_pessoa(
            pessoa_id,
            corpo.nome,
            corpo.faixa_etaria.value,
            corpo.perfil.value,
            acesso_vault,
        )
    except (sqlite3.IntegrityError, Conflito) as erro:
        raise HTTPException(status_code=409, detail="pessoa já existe") from erro


@router.get("/pessoas")
async def listar_pessoas(banco: DependenciaBanco):
    return await banco.listar_pessoas()


@router.get("/pessoas/{pessoa_id}")
async def obter_pessoa(
    pessoa_id: str,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    pessoa_id = _pessoa_do_usuario(usuario, pessoa_id)
    pessoa = await banco.obter_pessoa(pessoa_id)
    if pessoa is None:
        raise HTTPException(status_code=404, detail="pessoa não encontrada")
    return pessoa


@router.delete("/pessoas/{pessoa_id}", status_code=204)
async def apagar_pessoa(
    pessoa_id: str,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    pessoa_id = _pessoa_do_usuario(usuario, pessoa_id)
    if not await banco.apagar_pessoa(pessoa_id):
        raise HTTPException(status_code=404, detail="pessoa não encontrada")
    return Response(status_code=204)


@router.post("/pessoas/{pessoa_id}/memorias", status_code=201)
async def criar_memoria(
    pessoa_id: str,
    corpo: MemoriaEntrada,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    pessoa_id = _pessoa_do_usuario(usuario, pessoa_id)
    await _exigir_pessoa(banco, pessoa_id)
    if contem_segredo(corpo.texto):
        raise HTTPException(
            status_code=422, detail="a memória parece conter dado sensível"
        )
    return await banco.criar_memoria(
        pessoa_id, corpo.texto, corpo.categoria.value
    )


@router.get("/pessoas/{pessoa_id}/memorias")
async def listar_memorias(
    pessoa_id: str,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    pessoa_id = _pessoa_do_usuario(usuario, pessoa_id)
    await _exigir_pessoa(banco, pessoa_id)
    return await banco.listar_memorias(pessoa_id)


@router.delete("/pessoas/{pessoa_id}/memorias/{memoria_id}", status_code=204)
async def apagar_memoria(
    pessoa_id: str,
    memoria_id: str,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    pessoa_id = _pessoa_do_usuario(usuario, pessoa_id)
    if not await banco.apagar_memoria(pessoa_id, memoria_id):
        raise HTTPException(status_code=404, detail="memória não encontrada")
    return Response(status_code=204)


@router.post("/pessoas/{pessoa_id}/nao_mencionar", status_code=201)
async def adicionar_tema(
    pessoa_id: str,
    corpo: TemaEntrada,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    pessoa_id = _pessoa_do_usuario(usuario, pessoa_id)
    await _exigir_pessoa(banco, pessoa_id)
    criado = await banco.adicionar_tema(pessoa_id, corpo.tema)
    if not criado:
        raise HTTPException(status_code=409, detail="tema já silenciado")
    return {"pessoa_id": pessoa_id, "tema": corpo.tema}


@router.get("/pessoas/{pessoa_id}/nao_mencionar")
async def listar_temas(
    pessoa_id: str,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    pessoa_id = _pessoa_do_usuario(usuario, pessoa_id)
    await _exigir_pessoa(banco, pessoa_id)
    return await banco.listar_temas(pessoa_id)


@router.delete(
    "/pessoas/{pessoa_id}/nao_mencionar/{tema}", status_code=204
)
async def remover_tema(
    pessoa_id: str,
    tema: str,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    pessoa_id = _pessoa_do_usuario(usuario, pessoa_id)
    if not await banco.remover_tema(pessoa_id, tema):
        raise HTTPException(status_code=404, detail="tema não encontrado")
    return Response(status_code=204)


@router.post("/pessoas/{pessoa_id}/ajustes", status_code=201)
async def criar_ajuste(
    pessoa_id: str,
    corpo: AjusteEntrada,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    pessoa_id = _pessoa_do_usuario(usuario, pessoa_id)
    await _exigir_pessoa(banco, pessoa_id)
    try:
        validados = validar_ajustes(
            [
                AjusteAprendido(
                    tipo=corpo.tipo,
                    texto=corpo.texto,
                    valor=corpo.valor,
                    origem=corpo.origem,
                )
            ]
        )
    except AjusteInvalido as erro:
        raise HTTPException(status_code=422, detail=erro.mensagem) from erro

    ajuste = validados[0]
    return await banco.criar_ajuste(
        pessoa_id,
        ajuste.tipo.value,
        ajuste.texto,
        ajuste.valor,
        ajuste.origem.value,
    )


@router.get("/pessoas/{pessoa_id}/ajustes")
async def listar_ajustes(
    pessoa_id: str,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    pessoa_id = _pessoa_do_usuario(usuario, pessoa_id)
    await _exigir_pessoa(banco, pessoa_id)
    return await banco.listar_ajustes(pessoa_id)


@router.delete("/pessoas/{pessoa_id}/ajustes/{ajuste_id}", status_code=204)
async def apagar_ajuste(
    pessoa_id: str,
    ajuste_id: str,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    pessoa_id = _pessoa_do_usuario(usuario, pessoa_id)
    if not await banco.apagar_ajuste(pessoa_id, ajuste_id):
        raise HTTPException(status_code=404, detail="ajuste não encontrado")
    return Response(status_code=204)


@router.get("/pessoas/{pessoa_id}/conversas")
async def listar_conversas(
    pessoa_id: str,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    pessoa_id = _pessoa_do_usuario(usuario, pessoa_id)
    await _exigir_pessoa(banco, pessoa_id)
    return await banco.listar_conversas(pessoa_id)


@router.get("/conversas/{conversa_id}/mensagens")
async def listar_mensagens(conversa_id: str, banco: DependenciaBanco):
    if await banco.obter_conversa(conversa_id) is None:
        raise HTTPException(status_code=404, detail="conversa não encontrada")
    return await banco.listar_mensagens(conversa_id)


@router.post("/chat")
async def chat(
    corpo: ChatEntrada,
    request: Request,
    banco: DependenciaBanco,
    llm: DependenciaLLM,
    personality: DependenciaPersonality,
    config: DependenciaConfig,
    usuario: DependenciaUsuario,
):
    pessoa_id = _pessoa_do_usuario(usuario, corpo.pessoa_id)
    linha_pessoa = await banco.obter_pessoa(pessoa_id)
    if linha_pessoa is None:
        raise HTTPException(status_code=404, detail="pessoa não encontrada")

    if corpo.conversa_id is not None:
        conversa = await banco.obter_conversa(corpo.conversa_id)
        if conversa is None or conversa["pessoa_id"] != pessoa_id:
            raise HTTPException(status_code=404, detail="conversa não encontrada")
    else:
        conversa = await banco.criar_conversa(pessoa_id)

    historico = await banco.ultimas_mensagens(
        conversa["id"], config.max_history_mensagens
    )
    _cortar_historico(historico, config.max_history_chars)

    await banco.criar_mensagem(conversa["id"], "user", corpo.mensagem)

    system = await _montar_system(
        personality, linha_pessoa, banco, config, corpo.mensagem
    )
    mensagens = [{"role": "system", "content": system}]
    mensagens.extend(
        {"role": linha["papel"], "content": linha["conteudo"]} for linha in historico
    )
    mensagens.append({"role": "user", "content": corpo.mensagem})

    if not corpo.stream:
        return await _resposta_unica(
            banco, llm, config, conversa["id"], mensagens
        )

    return await _resposta_stream(
        request, banco, llm, config, conversa["id"], mensagens
    )


async def _montar_system(
    personality: Personality,
    linha_pessoa: dict,
    banco: Banco,
    config: Config,
    mensagem: str,
) -> str:
    pessoa = Pessoa(
        nome=linha_pessoa["nome"],
        faixa_etaria=FaixaEtaria(linha_pessoa["faixa_etaria"]),
        perfil=Perfil(linha_pessoa["perfil"]),
    )
    ajustes = [
        AjusteAprendido(
            tipo=TipoAjuste(linha["tipo"]),
            texto=linha["texto"],
            valor=linha["valor"],
            origem=OrigemAjuste(linha["origem"]),
            criado_em=_data(linha["criada_em"]),
        )
        for linha in await banco.listar_ajustes(linha_pessoa["id"])
    ]
    memoria = MemoriaDaPessoa(
        fatos=tuple(
            Fato(
                linha["texto"],
                CategoriaFato(linha["categoria"]),
                _data(linha["criada_em"]),
            )
            for linha in await banco.listar_memorias(linha_pessoa["id"])
        ),
        nao_mencionar=tuple(await banco.listar_temas(linha_pessoa["id"])),
    )
    trechos = await _buscar_contexto(banco, linha_pessoa, config, mensagem)
    return montar(
        personality,
        pessoa,
        ajustes,
        memoria,
        trechos,
        max_chars_contexto=config.max_chars_contexto,
    ).render()


async def _buscar_contexto(
    banco: Banco, linha_pessoa: dict, config: Config, mensagem: str
) -> list[Trecho]:
    if not linha_pessoa.get("acesso_vault"):
        return []
    linhas = await banco.buscar_trechos(mensagem, config.max_trechos_contexto)
    return [
        Trecho(nota=linha["nota"], secao=linha["secao"], texto=linha["texto"])
        for linha in linhas
    ]


async def _resposta_unica(
    banco: Banco,
    llm: ClienteLLM,
    config: Config,
    conversa_id: str,
    mensagens: list[dict],
) -> dict:
    partes: list[str] = []
    uso: Uso | None = None
    try:
        async for evento in llm.stream(
            mensagens,
            temperatura=config.temperatura,
            max_tokens=config.max_tokens,
        ):
            if isinstance(evento, Delta):
                partes.append(evento.texto)
            elif isinstance(evento, Fim):
                uso = evento.uso
    except ErroDoProvedor as erro:
        logger.warning("provedor falhou: %s", erro.detalhe)
        raise HTTPException(
            status_code=502, detail=f"provedor falhou: {erro.detalhe}"
        ) from erro

    texto = "".join(partes)
    mensagem = await banco.criar_mensagem(conversa_id, "assistant", texto)
    return {
        "conversa_id": conversa_id,
        "mensagem_id": mensagem["id"],
        "resposta": texto,
        "modelo": config.llm_model,
        "uso": _uso_dict(uso),
    }


async def _resposta_stream(
    request: Request,
    banco: Banco,
    llm: ClienteLLM,
    config: Config,
    conversa_id: str,
    mensagens: list[dict],
) -> StreamingResponse:
    fluxo = llm.stream(
        mensagens,
        temperatura=config.temperatura,
        max_tokens=config.max_tokens,
    )
    try:
        primeiro = await anext(fluxo)
    except StopAsyncIteration:
        primeiro = None
    except ErroDoProvedor as erro:
        logger.warning("provedor falhou antes do stream: %s", erro.detalhe)
        raise HTTPException(
            status_code=502, detail=f"provedor falhou: {erro.detalhe}"
        ) from erro

    async def gerar():
        partes: list[str] = []
        uso: Uso | None = None
        try:
            async for evento in _encadear(primeiro, fluxo):
                if isinstance(evento, Delta):
                    partes.append(evento.texto)
                    yield _sse("token", {"texto": evento.texto})
                elif isinstance(evento, Fim):
                    uso = evento.uso

            if await request.is_disconnected():
                if partes:
                    await banco.criar_mensagem(
                        conversa_id, "assistant", "".join(partes), "interrompida"
                    )
                return

            mensagem = await banco.criar_mensagem(
                conversa_id, "assistant", "".join(partes)
            )
            yield _sse(
                "done",
                {
                    "conversa_id": conversa_id,
                    "mensagem_id": mensagem["id"],
                    "modelo": config.llm_model,
                    "uso": _uso_dict(uso),
                },
            )
        except asyncio.CancelledError:
            if partes:
                with anyio.CancelScope(shield=True):
                    await banco.criar_mensagem(
                        conversa_id, "assistant", "".join(partes), "interrompida"
                    )
            raise
        except ErroDoProvedor as erro:
            logger.warning("provedor falhou no meio do stream: %s", erro.detalhe)
            if partes:
                await banco.criar_mensagem(
                    conversa_id, "assistant", "".join(partes), "erro"
                )
            yield _sse("error", {"codigo": "llm_falhou", "detalhe": erro.detalhe})
        except Exception:
            logger.exception("falha inesperada no stream")
            if partes:
                await banco.criar_mensagem(
                    conversa_id, "assistant", "".join(partes), "erro"
                )
            yield _sse(
                "error", {"codigo": "interno", "detalhe": "falha inesperada"}
            )

    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _encadear(primeiro, fluxo):
    if primeiro is not None:
        yield primeiro
    async for evento in fluxo:
        yield evento


def _cortar_historico(historico: list[dict], limite: int) -> None:
    total = sum(len(mensagem["conteudo"]) for mensagem in historico)
    while historico and total > limite:
        total -= len(historico.pop(0)["conteudo"])


def _sse(evento: str, dados: dict) -> str:
    return f"event: {evento}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"


def _uso_dict(uso: Uso | None) -> dict | None:
    if uso is None:
        return None
    return {
        "prompt_tokens": uso.prompt_tokens,
        "completion_tokens": uso.completion_tokens,
        "total_tokens": uso.total_tokens,
    }


def _data(iso: str):
    return datetime.fromisoformat(iso).date()


async def _exigir_pessoa(banco: Banco, pessoa_id: str) -> None:
    if await banco.obter_pessoa(pessoa_id) is None:
        raise HTTPException(status_code=404, detail="pessoa não encontrada")
