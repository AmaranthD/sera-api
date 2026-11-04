from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated

import anyio
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
)
from fastapi.responses import JSONResponse, StreamingResponse

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
from .busca import BuscaIndisponivel, ClienteTavily, ResultadoBusca
from .config import Config
from .db import Banco
from .db_supabase import Conflito
from .ferramentas import (
    INSTRUCAO_AGENDA,
    INSTRUCAO_BUSCA,
    INSTRUCAO_JW,
    INSTRUCAO_JW_MODO,
    INSTRUCAO_MEMORIA,
    INSTRUCAO_TEXTO_DIARIO,
    NOME_AGENDAR,
    NOME_AJUSTAR,
    NOME_CANCELAR_COMPROMISSO,
    NOME_CONSULTAR_AGENDA,
    NOME_ESQUECER,
    NOME_JW,
    NOME_LEMBRAR,
    NOME_PESQUISA,
    NOME_TEXTO_DIARIO,
    ContextoFerramentas,
    FerramentaDesconhecida,
    FerramentaInvalida,
    bloco_resultados,
    consulta_esquecimento,
    consulta_explicita,
    esquemas,
    executar_ferramenta,
    ferramentas_jw_para,
    fontes_jw,
    formatar_resultado_jw,
    referencia_biblica,
)
from .jw import JWIndisponivel
from .jw_conteudo import (
    ConteudoJWIndisponivel,
    URLJWInvalida,
    buscar_conteudo_jw,
)
from .llm import (
    ChamadaFerramenta,
    ClienteLLM,
    Delta,
    ErroDoProvedor,
    Ferramenta,
    Fim,
    Uso,
)
from .tempo import agora as agora_do_fuso
from .relogio import bloco_agora, normalizar_consulta
from .schemas import (
    AjusteAtualizacao,
    AjusteEntrada,
    ChatEntrada,
    MemoriaAtualizacao,
    MemoriaEntrada,
    PessoaEntrada,
    TemaEntrada,
)
from .webpush import (
    FalhaPush,
    NotificacoesIndisponiveis,
    enviar_push,
    payload_mensagem,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@dataclass(frozen=True)
class Pesquisando:
    consulta: str


@dataclass(frozen=True)
class Fontes:
    fontes: tuple[dict, ...]


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


def _modo_jw(config: Config, fonte: str | None) -> bool:
    modo = fonte == "jw"
    if modo and not (config.jw_ativa and config.llm_provider == "openai"):
        raise HTTPException(
            status_code=503,
            detail="o modo JW não está disponível neste servidor",
        )
    return modo


async def _conversa_do_chat(
    banco: Banco,
    pessoa_id: str,
    conversa_id: str | None,
    mensagem: str,
) -> dict:
    if conversa_id is not None:
        conversa = await banco.obter_conversa(conversa_id)
        if conversa is None or conversa["pessoa_id"] != pessoa_id:
            raise HTTPException(
                status_code=404, detail="conversa não encontrada"
            )
        return conversa
    return await banco.criar_conversa(
        pessoa_id, _titulo_da_mensagem(mensagem)
    )


@router.get("/jw/conteudo")
async def conteudo_jw(
    usuario: DependenciaUsuario,
    url: str = Query(..., min_length=8, max_length=2000),
):
    """Conteúdo legível de uma página do jw.org para o modal do chat."""
    del usuario
    try:
        conteudo = await buscar_conteudo_jw(url)
    except URLJWInvalida as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro
    except ConteudoJWIndisponivel as erro:
        raise HTTPException(status_code=503, detail=str(erro)) from erro
    return {
        "titulo": conteudo.titulo,
        "paragrafos": list(conteudo.paragrafos),
        "url": conteudo.url,
    }


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
async def listar_pessoas(
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    # Com auth, a resposta é sempre a pessoa do token. Não confie só no RLS
    # nem devolva a lista inteira: um cliente antigo/cache poderia pegar o
    # perfil de outra conta.
    if usuario is not None:
        pessoa = await banco.obter_pessoa(usuario.id)
        return [pessoa] if pessoa is not None else []
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


@router.patch("/pessoas/{pessoa_id}/memorias/{memoria_id}")
async def atualizar_memoria(
    pessoa_id: str,
    memoria_id: str,
    corpo: MemoriaAtualizacao,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    pessoa_id = _pessoa_do_usuario(usuario, pessoa_id)
    await _exigir_pessoa(banco, pessoa_id)
    if corpo.texto is None and corpo.categoria is None:
        raise HTTPException(status_code=422, detail="nada para atualizar")

    memorias = await banco.listar_memorias(pessoa_id)
    atual = next((item for item in memorias if item["id"] == memoria_id), None)
    if atual is None:
        raise HTTPException(status_code=404, detail="memória não encontrada")

    texto = (corpo.texto or atual["texto"]).strip()
    if contem_segredo(texto):
        raise HTTPException(
            status_code=422, detail="a memória parece conter dado sensível"
        )
    categoria = CategoriaFato(corpo.categoria or atual["categoria"])

    atualizada = await banco.atualizar_memoria(
        pessoa_id, memoria_id, texto, categoria.value
    )
    if atualizada is None:
        raise HTTPException(status_code=404, detail="memória não encontrada")
    return atualizada


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


@router.patch("/pessoas/{pessoa_id}/ajustes/{ajuste_id}")
async def atualizar_ajuste(
    pessoa_id: str,
    ajuste_id: str,
    corpo: AjusteAtualizacao,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    pessoa_id = _pessoa_do_usuario(usuario, pessoa_id)
    await _exigir_pessoa(banco, pessoa_id)
    if corpo.texto is None and corpo.valor is None:
        raise HTTPException(status_code=422, detail="nada para atualizar")

    ajustes = await banco.listar_ajustes(pessoa_id)
    atual = next((item for item in ajustes if item["id"] == ajuste_id), None)
    if atual is None:
        raise HTTPException(status_code=404, detail="ajuste não encontrado")

    try:
        validado = validar_ajustes(
            [
                AjusteAprendido(
                    tipo=TipoAjuste(atual["tipo"]),
                    texto=(
                        corpo.texto
                        if corpo.texto is not None
                        else atual.get("texto")
                    ),
                    valor=(
                        corpo.valor
                        if corpo.valor is not None
                        else atual.get("valor")
                    ),
                    origem=OrigemAjuste(atual["origem"]),
                )
            ]
        )[0]
    except AjusteInvalido as erro:
        raise HTTPException(status_code=422, detail=erro.mensagem) from erro

    atualizado = await banco.atualizar_ajuste(
        pessoa_id, ajuste_id, validado.texto, validado.valor
    )
    if atualizado is None:
        raise HTTPException(status_code=404, detail="ajuste não encontrado")
    return atualizado


@router.get("/pessoas/{pessoa_id}/conversas")
async def listar_conversas(
    pessoa_id: str,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    pessoa_id = _pessoa_do_usuario(usuario, pessoa_id)
    await _exigir_pessoa(banco, pessoa_id)
    return await banco.listar_conversas(pessoa_id)


@router.get("/pessoas/{pessoa_id}/dados")
async def exportar_dados(
    pessoa_id: str,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    """Exporta tudo o que a Sera sabe sobre a pessoa (LGPD)."""
    pessoa_id = _pessoa_do_usuario(usuario, pessoa_id)
    pessoa = await banco.obter_pessoa(pessoa_id)
    if pessoa is None:
        raise HTTPException(status_code=404, detail="pessoa não encontrada")

    conversas = await banco.listar_conversas(pessoa_id)
    for conversa in conversas:
        conversa["mensagens"] = await banco.listar_mensagens(conversa["id"])

    dados = {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pessoa": pessoa,
        "memorias": await banco.listar_memorias(pessoa_id),
        "ajustes": await banco.listar_ajustes(pessoa_id),
        "conversas": conversas,
    }
    return JSONResponse(
        content=dados,
        headers={
            "Content-Disposition": 'attachment; filename="sera-dados.json"'
        },
    )


@router.get("/conversas/{conversa_id}/mensagens")
async def listar_mensagens(
    conversa_id: str,
    request: Request,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    conversa = await banco.obter_conversa(conversa_id)
    # Não confie só no RLS/SQLite: com auth, a conversa precisa ser da
    # própria pessoa mesmo que o id seja adivinhado.
    if conversa is None or (
        usuario is not None and conversa["pessoa_id"] != usuario.id
    ):
        raise HTTPException(status_code=404, detail="conversa não encontrada")

    mensagens = await banco.listar_mensagens(conversa_id)
    jobs = request.app.state.jobs
    for mensagem in mensagens:
        if mensagem.get("status") != "gerando":
            continue
        if jobs.ativa(mensagem["id"]):
            continue
        # Job órfão (reinício do servidor ou cancelamento): não deixa a
        # conversa presa em "gerando" para sempre.
        atualizada = await banco.atualizar_mensagem(
            mensagem["id"],
            mensagem["conteudo"],
            "interrompida",
            mensagem.get("fontes"),
        )
        if atualizada is not None:
            mensagem.update(atualizada)
    return mensagens


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

    modo_jw = _modo_jw(config, corpo.fonte)
    if modo_jw:
        aquecer_jw = getattr(
            getattr(request.app.state, "jw", None), "aquecer", None
        )
        if callable(aquecer_jw):
            try:
                await aquecer_jw(limite=min(60.0, config.jw_timeout))
            except JWIndisponivel as erro:
                logger.warning("serviço JW não acordou: %s", erro.detalhe)
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "o serviço JW não respondeu; tente de novo em "
                        "alguns instantes"
                    ),
                ) from erro

    conversa = await _conversa_do_chat(
        banco, pessoa_id, corpo.conversa_id, corpo.mensagem
    )

    historico = await banco.ultimas_mensagens(
        conversa["id"], config.max_history_mensagens
    )
    _cortar_historico(historico, config.max_history_chars)

    mensagem_usuario = await banco.criar_mensagem(
        conversa["id"], "user", corpo.mensagem
    )

    momento = agora_do_fuso(config.fuso_horario)
    system = await _montar_system(
        personality, linha_pessoa, banco, config, corpo.mensagem, momento
    )
    busca, ferramentas, fontes, system = await _preparar_ferramentas(
        request.app, config, corpo.mensagem, system, momento, modo_jw=modo_jw
    )
    contexto = ContextoFerramentas(
        busca=busca,
        jw=getattr(request.app.state, "jw", None),
        banco=banco,
        pessoa_id=pessoa_id,
        mensagem_usuario=corpo.mensagem,
        config=config,
    )
    system, esqueceu = await _aplicar_esquecimento(
        config, corpo.mensagem, system, contexto
    )
    if esqueceu and ferramentas:
        ferramentas = [
            ferramenta
            for ferramenta in ferramentas
            if ferramenta["function"]["name"] != NOME_ESQUECER
        ] or None
    mensagens = [{"role": "system", "content": system}]
    mensagens.extend(
        {"role": linha["papel"], "content": linha["conteudo"]} for linha in historico
    )
    mensagens.append({"role": "user", "content": corpo.mensagem})

    if not corpo.stream:
        return await _resposta_unica(
            banco,
            llm,
            config,
            conversa["id"],
            mensagens,
            contexto=contexto,
            ferramentas=ferramentas,
            momento=momento,
            uma_fonte=modo_jw,
        )

    return await _resposta_stream(
        request,
        banco,
        llm,
        config,
        conversa["id"],
        mensagem_usuario["id"],
        mensagens,
        contexto=contexto,
        ferramentas=ferramentas,
        fontes=fontes,
        momento=momento,
        uma_fonte=modo_jw,
    )


@router.post("/chat/job", status_code=202)
async def chat_job(
    corpo: ChatEntrada,
    request: Request,
    banco: DependenciaBanco,
    config: DependenciaConfig,
    usuario: DependenciaUsuario,
):
    """Inicia a resposta em segundo plano e devolve os IDs para polling."""
    pessoa_id = _pessoa_do_usuario(usuario, corpo.pessoa_id)
    linha_pessoa = await banco.obter_pessoa(pessoa_id)
    if linha_pessoa is None:
        raise HTTPException(status_code=404, detail="pessoa não encontrada")

    modo_jw = _modo_jw(config, corpo.fonte)
    conversa = await _conversa_do_chat(
        banco, pessoa_id, corpo.conversa_id, corpo.mensagem
    )

    jobs = request.app.state.jobs
    # A checagem e a criação precisam ser atômicas: dois pedidos simultâneos
    # na mesma conversa não podem abrir duas respostas `gerando`.
    async with jobs.trancar():
        await banco.marcar_gerando_interrompidas(conversa["id"], 600)
        em_andamento = await banco.mensagem_gerando(conversa["id"])
        if em_andamento is not None:
            if jobs.ativa(em_andamento["id"]):
                raise HTTPException(
                    status_code=409,
                    detail="já existe uma resposta em andamento",
                )
            # Job órfão (servidor reiniciou): libera a conversa.
            await banco.atualizar_mensagem(
                em_andamento["id"],
                em_andamento["conteudo"],
                "interrompida",
                em_andamento.get("fontes"),
            )

        mensagem_usuario = await banco.criar_mensagem(
            conversa["id"], "user", corpo.mensagem
        )
        resposta = await banco.criar_mensagem(
            conversa["id"], "assistant", "", "gerando"
        )

        fabrica = getattr(request.app.state, "banco_fabrica", None)
        if fabrica is not None:
            banco_job = fabrica(usuario.token if usuario else None)
            fechar_banco = True
        else:
            banco_job = request.app.state.banco
            fechar_banco = False

        jobs.iniciar(
            resposta["id"],
            _rodar_job(
                request.app,
                banco_job,
                config,
                linha_pessoa,
                conversa["id"],
                corpo.mensagem,
                resposta["id"],
                modo_jw,
                fechar_banco,
            ),
        )
    logger.info(
        "job de chat iniciado: conversa=%s resposta=%s",
        conversa["id"],
        resposta["id"],
    )
    return {
        "conversa_id": conversa["id"],
        "mensagem_id": mensagem_usuario["id"],
        "resposta_id": resposta["id"],
        "status": "gerando",
    }


async def _resposta_da_pessoa(
    resposta_id: str,
    banco: Banco,
    usuario: Usuario | None,
) -> dict:
    """Busca a resposta garantindo que ela pertence a quem pediu."""
    mensagem = await banco.obter_mensagem(resposta_id)
    if mensagem is None:
        raise HTTPException(status_code=404, detail="resposta não encontrada")
    conversa = await banco.obter_conversa(mensagem["conversa_id"])
    if conversa is None:
        raise HTTPException(status_code=404, detail="resposta não encontrada")
    if usuario is not None and conversa["pessoa_id"] != usuario.id:
        raise HTTPException(status_code=404, detail="resposta não encontrada")
    return mensagem


@router.get("/chat/job/{resposta_id}")
async def estado_job(
    resposta_id: str,
    request: Request,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    """Estado de uma resposta, para o app acompanhar só ela no polling."""
    mensagem = await _resposta_da_pessoa(resposta_id, banco, usuario)
    if mensagem["status"] == "gerando" and not request.app.state.jobs.ativa(
        resposta_id
    ):
        # Job órfão (reinício do servidor): não deixa preso em "gerando".
        atualizada = await banco.atualizar_mensagem(
            resposta_id,
            mensagem["conteudo"],
            "interrompida",
            mensagem.get("fontes"),
        )
        if atualizada is not None:
            mensagem = atualizada
    return mensagem


@router.post("/chat/job/{resposta_id}/cancelar", status_code=204)
async def cancelar_job(
    resposta_id: str,
    request: Request,
    banco: DependenciaBanco,
    usuario: DependenciaUsuario,
):
    mensagem = await _resposta_da_pessoa(resposta_id, banco, usuario)

    if not request.app.state.jobs.cancelar(resposta_id) and (
        mensagem["status"] == "gerando"
    ):
        await banco.atualizar_mensagem(
            resposta_id,
            mensagem["conteudo"],
            "interrompida",
            mensagem.get("fontes"),
        )
    return Response(status_code=204)


async def _notificar_resposta(
    banco: Banco,
    config: Config,
    pessoa_id: str,
    conversa_id: str,
    resposta_id: str,
    texto: str,
    *,
    erro: bool = False,
) -> None:
    """Avisa por Web Push que o job terminou, sem derrubar o job."""
    if not config.notificacoes_ativas:
        return
    try:
        inscricoes = await banco.listar_inscricoes(pessoa_id)
    except Exception:
        logger.exception("falha ao listar inscrições da resposta pronta")
        return
    if not inscricoes:
        return

    payload = payload_mensagem(
        conversa_id,
        resposta_id,
        texto,
        erro=erro,
        preview=config.notificacoes_preview,
    )
    for inscricao in inscricoes:
        try:
            await enviar_push(inscricao, payload, config)
        except FalhaPush as falha:
            if falha.inscricao_morta:
                await banco.apagar_inscricao_por_endpoint(
                    inscricao["endpoint"]
                )
        except NotificacoesIndisponiveis as falha:
            logger.warning("push indisponível: %s", falha)
            return
        except Exception:
            logger.exception("falha ao notificar resposta pronta")


async def _rodar_job(
    app: FastAPI,
    banco: Banco,
    config: Config,
    linha_pessoa: dict,
    conversa_id: str,
    texto: str,
    resposta_id: str,
    modo_jw: bool,
    fechar_banco: bool,
) -> None:
    """Gera e persiste a resposta sem depender do request que a criou."""
    partes: list[str] = []
    fontes: list[dict] = []
    ultimo_salvo = 0.0
    try:
        if modo_jw:
            aquecer = getattr(getattr(app.state, "jw", None), "aquecer", None)
            if callable(aquecer):
                try:
                    await aquecer(limite=min(60.0, config.jw_timeout))
                except JWIndisponivel as erro:
                    logger.warning(
                        "serviço JW não acordou no job: %s", erro.detalhe
                    )

        historico = await banco.ultimas_mensagens(
            conversa_id, config.max_history_mensagens
        )
        _cortar_historico(historico, config.max_history_chars)

        momento = agora_do_fuso(config.fuso_horario)
        system = await _montar_system(
            app.state.personality,
            linha_pessoa,
            banco,
            config,
            texto,
            momento,
        )
        busca, ferramentas, fontes_iniciais, system = (
            await _preparar_ferramentas(
                app,
                config,
                texto,
                system,
                momento,
                modo_jw=modo_jw,
            )
        )
        contexto = ContextoFerramentas(
            busca=busca,
            jw=getattr(app.state, "jw", None),
            banco=banco,
            pessoa_id=linha_pessoa["id"],
            mensagem_usuario=texto,
            config=config,
        )
        system, esqueceu = await _aplicar_esquecimento(
            config, texto, system, contexto
        )
        if esqueceu and ferramentas:
            ferramentas = [
                ferramenta
                for ferramenta in ferramentas
                if ferramenta["function"]["name"] != NOME_ESQUECER
            ] or None

        fontes = [dict(fonte) for fonte in fontes_iniciais]
        mensagens = [{"role": "system", "content": system}]
        mensagens.extend(
            {"role": linha["papel"], "content": linha["conteudo"]}
            for linha in historico
        )
        mensagens.append({"role": "user", "content": texto})

        async for evento in _fluxo_com_ferramentas(
            app.state.llm,
            mensagens,
            config,
            contexto,
            ferramentas,
            momento,
            uma_fonte=modo_jw,
        ):
            if isinstance(evento, Delta):
                partes.append(evento.texto)
            elif isinstance(evento, Fontes):
                for fonte in evento.fontes:
                    if all(item["url"] != fonte["url"] for item in fontes):
                        fontes.append(dict(fonte))

            instante = time.monotonic()
            if instante - ultimo_salvo >= 1.2:
                await banco.atualizar_mensagem(
                    resposta_id, "".join(partes), "gerando", fontes
                )
                ultimo_salvo = instante

        resposta = "".join(partes)
        await banco.atualizar_mensagem(
            resposta_id, resposta, "completa", fontes
        )
        await _notificar_resposta(
            banco,
            config,
            linha_pessoa["id"],
            conversa_id,
            resposta_id,
            resposta,
        )
        logger.info("job de chat concluído: resposta=%s", resposta_id)
    except asyncio.CancelledError:
        with anyio.CancelScope(shield=True):
            await banco.atualizar_mensagem(
                resposta_id, "".join(partes), "interrompida", fontes
            )
        logger.info("job de chat cancelado: resposta=%s", resposta_id)
        raise
    except ErroDoProvedor as erro:
        logger.warning("provedor falhou no job: %s", erro.detalhe)
        await banco.atualizar_mensagem(
            resposta_id, "".join(partes), "erro", fontes
        )
        await _notificar_resposta(
            banco,
            config,
            linha_pessoa["id"],
            conversa_id,
            resposta_id,
            "",
            erro=True,
        )
    except Exception:
        logger.exception("falha inesperada no job de chat")
        await banco.atualizar_mensagem(
            resposta_id, "".join(partes), "erro", fontes
        )
        await _notificar_resposta(
            banco,
            config,
            linha_pessoa["id"],
            conversa_id,
            resposta_id,
            "",
            erro=True,
        )
    finally:
        if fechar_banco:
            fechar = getattr(banco, "fechar", None)
            if fechar is not None:
                await fechar()


async def _preparar_ferramentas(
    app: FastAPI,
    config: Config,
    mensagem: str,
    system: str,
    momento: datetime,
    *,
    modo_jw: bool = False,
) -> tuple[ClienteTavily | None, list[dict] | None, list[dict], str]:
    """Liga busca e aprendizado e, no pedido explícito, já busca antes.

    "Pesquise X" é interpretado como busca na internet sem depender de o
    modelo decidir chamar a ferramenta. No modo JW a internet fica desligada
    e a única fonte é o serviço JW.
    """
    busca: ClienteTavily | None = getattr(app.state, "busca", None)
    if not config.busca_ativa or modo_jw:
        busca = None

    # O cliente Gemini desta camada ainda não executa tool calling.
    tool_calling = config.llm_provider == "openai"
    aprendizado = config.aprendizado_habilitado and tool_calling
    agenda = tool_calling and not modo_jw
    jw = config.jw_ativa and tool_calling
    texto_diario = tool_calling
    ferramentas = esquemas(
        busca=busca is not None and tool_calling,
        aprendizado=aprendizado,
        agenda=agenda,
        jw=jw,
        jw_ferramentas=ferramentas_jw_para(mensagem) if modo_jw else None,
        texto_diario=texto_diario,
    )
    if jw:
        system = f"{system}\n\n{INSTRUCAO_JW}"
    if agenda:
        system = f"{system}\n\n{INSTRUCAO_AGENDA}"
    if texto_diario:
        system = f"{system}\n\n{INSTRUCAO_TEXTO_DIARIO}"
    fontes: list[dict] = []
    if modo_jw:
        system = f"{system}\n\n{INSTRUCAO_JW_MODO}"
        referencia = referencia_biblica(mensagem)
        cliente_jw = getattr(app.state, "jw", None)
        if referencia is not None and jw and cliente_jw is not None:
            livro, capitulo, inicio, fim = referencia
            verso = f"{inicio}-{fim}" if fim is not None else str(inicio)
            argumentos: dict = {
                "book": livro,
                "chapter": capitulo,
                "verse": verso,
                "fields": ["verses", "study_notes"],
            }
            try:
                resposta = await cliente_jw.executar(
                    "get_verse_with_study", argumentos
                )
            except JWIndisponivel as erro:
                logger.warning(
                    "consulta JW da referência falhou: %s", erro.detalhe
                )
                system = (
                    f"{system}\n\n## Conteúdo JW\n"
                    "A consulta do versículo falhou agora. Avise que não "
                    "conseguiu acessar o conteúdo JW e não invente o texto."
                )
            else:
                formatado = formatar_resultado_jw(
                    resposta.ferramenta, resposta.texto
                )
                limite = getattr(cliente_jw, "max_chars", None)
                if (
                    isinstance(limite, int)
                    and limite > 0
                    and len(formatado) > limite
                ):
                    formatado = f"{formatado[:limite].rstrip()}…"

                fontes = fontes_jw(
                    "get_verse_with_study", argumentos, resposta.texto
                )
                link = fontes[0]["url"] if fontes else ""
                system = (
                    f"{system}\n\n## Conteúdo JW (já consultado)\n"
                    f"{formatado}\n\n"
                    "Responda usando apenas este conteúdo. Não chame a "
                    "ferramenta de novo para este versículo. Termine com uma "
                    "seção `## Fontes` com este único link em Markdown: "
                    f"[Bíblia (jw.org)]({link})"
                )
                # Já temos o texto: tirar a ferramenta evita chamada
                # duplicada e o vazamento de marcação do modelo.
                ferramentas = [
                    item
                    for item in ferramentas
                    if item["function"]["name"] != NOME_JW
                ]
    if not ferramentas and busca is None:
        return None, None, fontes, system

    consulta = consulta_explicita(mensagem) if busca is not None else None

    if consulta is not None:
        consulta = normalizar_consulta(consulta, momento)
        try:
            resultados = await busca.pesquisar(consulta)
        except BuscaIndisponivel as erro:
            logger.warning("busca explícita falhou: %s", erro.detalhe)
            system = (
                f"{system}\n\n## Busca na internet\n"
                "A busca falhou agora. Responda sem inventar dados e avise "
                "que não conseguiu consultar a internet."
            )
        else:
            fontes = [resultado.como_dict() for resultado in resultados]
            system = f"{system}\n\n{bloco_resultados(consulta, resultados, momento)}"
        # Já buscou: tira a ferramenta de pesquisa para não repetir a consulta.
        ferramentas = [
            ferramenta
            for ferramenta in ferramentas
            if ferramenta["function"]["name"] != NOME_PESQUISA
        ]
    elif busca is not None and tool_calling:
        system = f"{system}\n\n{INSTRUCAO_BUSCA}"

    if aprendizado:
        system = f"{system}\n\n{INSTRUCAO_MEMORIA}"

    return busca, ferramentas or None, fontes, system


async def _aplicar_esquecimento(
    config: Config,
    mensagem: str,
    system: str,
    contexto: ContextoFerramentas,
) -> tuple[str, bool]:
    """Executa "esqueça X" sem depender de o modelo chamar a ferramenta.

    Devolve o system atualizado e se a memória foi realmente apagada (para
    retirar a ferramenta `esquecer` daquela resposta).
    """
    if not config.aprendizado_habilitado:
        return system, False

    alvo = consulta_esquecimento(mensagem)
    if alvo is None:
        return system, False

    try:
        resultado = await executar_ferramenta(
            NOME_ESQUECER, {"texto": alvo, "confirmado": True}, contexto
        )
    except (FerramentaDesconhecida, FerramentaInvalida):
        return system, False

    nota = _nota_de_ferramenta(NOME_ESQUECER, resultado)
    if not nota:
        return system, False
    return f"{system}\n\n## Memória\n{nota}", bool(resultado.get("ok"))


async def _montar_system(
    personality: Personality,
    linha_pessoa: dict,
    banco: Banco,
    config: Config,
    mensagem: str,
    momento: datetime,
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
    base = montar(
        personality,
        pessoa,
        ajustes,
        memoria,
        trechos,
        max_chars_contexto=config.max_chars_contexto,
    ).render()
    return f"{base}\n\n{bloco_agora(momento, config.fuso_horario)}"


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
    *,
    contexto: ContextoFerramentas | None = None,
    ferramentas: list[dict] | None = None,
    momento: datetime | None = None,
    uma_fonte: bool = False,
) -> dict:
    contexto = contexto or ContextoFerramentas()
    partes: list[str] = []
    uso: Uso | None = None
    try:
        async for evento in _fluxo_com_ferramentas(
            llm,
            mensagens,
            config,
            contexto,
            ferramentas,
            momento,
            uma_fonte=uma_fonte,
        ):
            if isinstance(evento, Delta):
                partes.append(evento.texto)
            elif isinstance(evento, Fim):
                uso = _somar_uso(uso, evento.uso)
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


async def _fluxo_com_ferramentas(
    llm: ClienteLLM,
    mensagens: list[dict],
    config: Config,
    contexto: ContextoFerramentas,
    ferramentas: list[dict] | None,
    momento: datetime | None = None,
    *,
    uma_fonte: bool = False,
):
    """Executa o loop de tool calling e emite Delta/Fim e eventos de busca.

    Os resultados entram no system prompt em vez de virarem mensagens
    `assistant`/`tool`: alguns modelos (MiniMax via NVIDIA NIM) vazam a
    marcação interna de tool call quando relê esse protocolo. Assim o modelo
    vê apenas system/user e, na última rodada, responde sem ferramentas.
    """
    conversa = [dict(mensagem) for mensagem in mensagens]
    rodadas = config.busca_max_rodadas if ferramentas else 0
    if contexto.jw is not None and ferramentas:
        rodadas = max(rodadas, config.jw_max_rodadas)
    chamadas: list[ChamadaFerramenta] = []
    fonte_principal: dict | None = None

    if rodadas == 0:
        async for evento in llm.stream(
            conversa,
            temperatura=config.temperatura,
            max_tokens=config.max_tokens,
            ferramentas=None,
        ):
            yield evento
        return

    for _ in range(rodadas):
        chamadas = []
        async for evento in llm.stream(
            conversa,
            temperatura=config.temperatura,
            max_tokens=config.max_tokens,
            ferramentas=ferramentas,
        ):
            if isinstance(evento, Ferramenta):
                chamadas.extend(evento.chamadas)
            else:
                yield evento

        if not chamadas:
            return

        for chamada in chamadas:
            if chamada.nome == NOME_PESQUISA:
                yield Pesquisando(_consulta_da_chamada(chamada, momento))

        blocos, fontes, notas = await _executar_chamadas(
            chamadas, contexto, momento
        )
        if fontes:
            if uma_fonte:
                if fonte_principal is None:
                    fonte_principal = fontes[0]
                    yield Fontes((fonte_principal,))
            else:
                yield Fontes(tuple(fontes))
        extras = blocos + notas
        if extras:
            conversa[0]["content"] = (
                f"{conversa[0].get('content') or ''}\n\n"
                + "\n\n".join(extras)
            )

    # Última rodada: mantém os esquemas (para o modelo não inventar um
    # formato de chamada), mas proíbe novas ferramentas. Também removemos a
    # instrução do modo JW: se ela fica, o MiniMax tenta chamar de novo e
    # vaza a marcação interna como texto.
    conteudo = f"{conversa[0].get('content') or ''}"
    for instrucao in (
        INSTRUCAO_BUSCA,
        INSTRUCAO_MEMORIA,
        INSTRUCAO_AGENDA,
        INSTRUCAO_JW,
        INSTRUCAO_JW_MODO,
        INSTRUCAO_TEXTO_DIARIO,
    ):
        conteudo = conteudo.replace(instrucao, "")
    conversa[0]["content"] = (
        f"{conteudo.strip()}\n\n"
        "## Agora\n"
        "Responda com o conteúdo já consultado, em português do Brasil, "
        "sem palavras ou caracteres de outros idiomas. Não chame ferramentas."
    )
    if uma_fonte and fonte_principal:
        titulo = fonte_principal.get("titulo") or "Fonte"
        url = fonte_principal.get("url") or ""
        if url:
            conversa[0]["content"] += (
                "\n\nTermine com uma seção `## Fontes` e apenas este link em "
                f"Markdown: [{titulo}]({url})."
            )
    async for evento in llm.stream(
        conversa,
        temperatura=config.temperatura,
        max_tokens=config.max_tokens,
        ferramentas=ferramentas,
        escolha_ferramenta="none",
    ):
        if not isinstance(evento, Ferramenta):
            yield evento


async def _executar_chamadas(
    chamadas: list[ChamadaFerramenta],
    contexto: ContextoFerramentas,
    momento: datetime | None = None,
) -> tuple[list[str], list[dict], list[str]]:
    blocos: list[str] = []
    fontes: list[dict] = []
    notas: list[str] = []
    vistos: set[str] = set()
    assinaturas: set[tuple[str, str]] = set()

    for chamada in chamadas:
        assinatura = (chamada.nome, _assinatura_argumentos(chamada.argumentos))
        if assinatura in assinaturas:
            # Alguns modelos repetem a mesma chamada na mesma rodada. Sem
            # isso, a segunda criação bateria no próprio compromisso/memória
            # criado pela primeira e a pessoa veria um conflito fantasma.
            logger.info(
                "ignorando chamada duplicada: %s", chamada.nome
            )
            continue
        assinaturas.add(assinatura)

        consulta = (
            _consulta_da_chamada(chamada, momento)
            if chamada.nome == NOME_PESQUISA
            else ""
        )
        argumentos = (
            {"consulta": consulta}
            if chamada.nome == NOME_PESQUISA
            else chamada.argumentos
        )
        try:
            resultado = await executar_ferramenta(
                chamada.nome, argumentos, contexto
            )
        except (
            FerramentaDesconhecida,
            FerramentaInvalida,
            BuscaIndisponivel,
            JWIndisponivel,
        ) as erro:
            logger.warning("ferramenta falhou: %s", erro)
            if chamada.nome == NOME_PESQUISA:
                blocos.append(
                    "## Busca na internet\n"
                    f'A busca por "{consulta}" falhou: {erro}. '
                    "Responda sem inventar dados e avise que não conseguiu "
                    "consultar a internet."
                )
            elif chamada.nome == NOME_JW:
                blocos.append(
                    "## Conteúdo JW\n"
                    f"A consulta JW falhou: {erro}. Avise que não conseguiu "
                    "consultar o conteúdo agora."
                )
            else:
                notas.append(
                    f"Não foi possível salvar ({chamada.nome}): {erro}."
                )
            continue

        if chamada.nome == NOME_PESQUISA:
            itens = resultado.get("resultados") or []
            resultados = [ResultadoBusca(**item) for item in itens]
            blocos.append(
                bloco_resultados(
                    resultado.get("consulta") or consulta,
                    resultados,
                    momento,
                )
            )
            for item in itens:
                url = item.get("url")
                if url and url not in vistos:
                    vistos.add(url)
                    fontes.append(item)
        elif chamada.nome == NOME_JW:
            texto = str(resultado.get("texto") or "").strip()
            ferramenta_jw = str(resultado.get("ferramenta") or "jw")
            if resultado.get("erro"):
                blocos.append(
                    "## Conteúdo JW\n"
                    f"A ferramenta JW retornou um erro: {texto}"
                )
            else:
                blocos.append(
                    "## Conteúdo JW\n"
                    f"{formatar_resultado_jw(ferramenta_jw, texto)}\n\n"
                    "Use apenas este conteúdo para responder e cite a URL "
                    "quando houver."
                )
                for item in resultado.get("fontes") or []:
                    url = str(item.get("url") or "")
                    if not url or url in vistos:
                        continue
                    vistos.add(url)
                    fontes.append(
                        {
                            "titulo": item.get("titulo") or "JW",
                            "url": url,
                        }
                    )
        else:
            notas.append(_nota_de_ferramenta(chamada.nome, resultado))

    return blocos, fontes, notas


def _nota_de_ferramenta(nome: str, resultado: dict) -> str:
    if nome == NOME_AGENDAR:
        if resultado.get("precisa_titulo"):
            return (
                "Antes de agendar, pergunte o título/assunto do "
                "compromisso. Não use 'exemplo', 'teste' nem invente um "
                "título."
            )
        if not resultado.get("ok"):
            conflito = resultado.get("conflito") or {}
            return (
                "Não agendei: o horário cruza com "
                f"“{conflito.get('titulo')}” ({conflito.get('inicio')} a "
                f"{conflito.get('fim')}). Mostre o conflito e pergunte "
                "outro horário."
            )
        compromisso = resultado.get("compromisso") or {}
        return (
            f"Agendei: {compromisso.get('titulo')} em "
            f"{compromisso.get('inicio')} até {compromisso.get('fim')} "
            f"(id {compromisso.get('id')})."
        )
    if nome == NOME_CONSULTAR_AGENDA:
        itens = resultado.get("compromissos") or []
        if not itens:
            return (
                "A agenda está vazia entre "
                f"{resultado.get('de')} e {resultado.get('ate')}."
            )
        linhas = "; ".join(
            f"{item.get('id')} — {item.get('titulo')} — "
            f"{item.get('inicio')} a {item.get('fim')}"
            for item in itens
        )
        return (
            f"Compromissos ({resultado.get('de')} a "
            f"{resultado.get('ate')}): {linhas}."
        )
    if nome == NOME_CANCELAR_COMPROMISSO:
        if resultado.get("ambigua"):
            opcoes = "; ".join(
                f"{item.get('id')} — {item.get('titulo')} — "
                f"{item.get('inicio')}"
                for item in resultado.get("candidatas") or []
            )
            return (
                "Há mais de um compromisso parecido: "
                f"{opcoes}. Pergunte qual cancelar."
            )
        if resultado.get("encontrado") is False or not resultado.get("ok"):
            return "Não encontrei esse compromisso na agenda."
        cancelado = resultado.get("cancelado") or {}
        return (
            f"Cancelei: {cancelado.get('titulo')} em "
            f"{cancelado.get('inicio')}."
        )
    if nome == NOME_TEXTO_DIARIO:
        if not resultado.get("ok"):
            return "Não consegui configurar o texto diário."
        if resultado.get("entrega"):
            entrega = resultado.get("entrega") or {}
            return (
                "Enviei o texto diário de "
                f"{entrega.get('dia')} na conversa “Texto diário”."
            )
        assinatura = resultado.get("assinatura") or {}
        if assinatura.get("ativo"):
            return (
                "Texto diário ativado para "
                f"{assinatura.get('hora')} ({assinatura.get('fuso')})."
            )
        return "Texto diário desativado."
    if nome == NOME_LEMBRAR:
        if resultado.get("precisa_confirmar"):
            return (
                "Antes de guardar, confirme com a pessoa: "
                f'"{resultado.get("texto")}". Só chame de novo com '
                "confirmado=true depois do sim."
            )
        if resultado.get("duplicada"):
            return "Essa memória já existia; nada novo foi salvo."
        memoria = resultado.get("memoria") or {}
        return f"Guardei na memória: {memoria.get('texto')}."
    if nome == NOME_AJUSTAR:
        if resultado.get("duplicado"):
            return "Essa preferência já estava registrada."
        ajuste = resultado.get("ajuste") or {}
        alvo = ajuste.get("texto") or ajuste.get("valor") or ""
        return f"Preferência atualizada: {ajuste.get('tipo')} = {alvo}."
    if nome == NOME_ESQUECER:
        if resultado.get("precisa_confirmar"):
            memoria = resultado.get("memoria") or {}
            return (
                "Antes de apagar, confirme com a pessoa: "
                f'"{memoria.get("texto")}". Só chame de novo com '
                "confirmado=true depois do sim."
            )
        if resultado.get("ambigua"):
            textos = "; ".join(
                f'"{item.get("texto")}"'
                for item in resultado.get("candidatas") or []
            )
            return (
                "Há mais de uma memória parecida: "
                f"{textos}. Pergunte qual delas apagar."
            )
        if resultado.get("encontrada") is False:
            return "Não encontrei nenhuma memória com esse teor."
        esquecida = resultado.get("esquecida") or {}
        if resultado.get("ok"):
            return f"Esqueci: {esquecida.get('texto')}."
        return "Não consegui apagar essa memória."
    return ""


def _assinatura_argumentos(argumentos: str) -> str:
    """Chave estável para reconhecer chamadas repetidas do modelo."""
    try:
        dados = json.loads(argumentos or "{}")
    except json.JSONDecodeError:
        return str(argumentos)
    if not isinstance(dados, dict):
        return str(argumentos)
    try:
        return json.dumps(dados, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(argumentos)


def _consulta_da_chamada(
    chamada: ChamadaFerramenta, momento: datetime | None = None
) -> str:
    try:
        dados = json.loads(chamada.argumentos or "{}")
    except json.JSONDecodeError:
        return ""
    if not isinstance(dados, dict):
        return ""
    consulta = " ".join(str(dados.get("consulta") or "").split())
    if momento is not None and consulta:
        consulta = normalizar_consulta(consulta, momento)
    return consulta


async def _resposta_stream(
    request: Request,
    banco: Banco,
    llm: ClienteLLM,
    config: Config,
    conversa_id: str,
    mensagem_usuario_id: str,
    mensagens: list[dict],
    *,
    contexto: ContextoFerramentas | None = None,
    ferramentas: list[dict] | None = None,
    fontes: list[dict] | None = None,
    momento: datetime | None = None,
    uma_fonte: bool = False,
) -> StreamingResponse:
    contexto = contexto or ContextoFerramentas()
    fluxo = _fluxo_com_ferramentas(
        llm,
        mensagens,
        config,
        contexto,
        ferramentas,
        momento,
        uma_fonte=uma_fonte,
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

    fontes_iniciais = list(fontes or [])
    if uma_fonte:
        fontes_iniciais = fontes_iniciais[:1]

    async def gerar():
        partes: list[str] = []
        uso: Uso | None = None
        yield _sse(
            "start",
            {
                "conversa_id": conversa_id,
                "mensagem_id": mensagem_usuario_id,
            },
        )
        if fontes_iniciais:
            yield _sse("sources", {"fontes": fontes_iniciais})
        try:
            async for evento in _encadear(primeiro, fluxo):
                if isinstance(evento, Delta):
                    partes.append(evento.texto)
                    yield _sse("token", {"texto": evento.texto})
                elif isinstance(evento, Fim):
                    uso = _somar_uso(uso, evento.uso)
                elif isinstance(evento, Pesquisando):
                    yield _sse(
                        "tool",
                        {
                            "nome": "pesquisar_web",
                            "consulta": evento.consulta,
                        },
                    )
                elif isinstance(evento, Fontes):
                    yield _sse("sources", {"fontes": list(evento.fontes)})

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


def _titulo_da_mensagem(texto: str, limite: int = 60) -> str:
    """Primeira frase da mensagem, curta o bastante para a lista lateral."""
    limpo = " ".join(texto.split())
    if len(limpo) <= limite:
        return limpo
    corte = limpo.rfind(" ", 0, limite)
    if corte < limite // 2:
        corte = limite
    return f"{limpo[:corte].rstrip(' ,.;:!?')}…"


def _uso_dict(uso: Uso | None) -> dict | None:
    if uso is None:
        return None
    return {
        "prompt_tokens": uso.prompt_tokens,
        "completion_tokens": uso.completion_tokens,
        "total_tokens": uso.total_tokens,
    }


def _somar_uso(atual: Uso | None, novo: Uso | None) -> Uso | None:
    if novo is None:
        return atual
    if atual is None:
        return novo
    return Uso(
        prompt_tokens=_somar_token(atual.prompt_tokens, novo.prompt_tokens),
        completion_tokens=_somar_token(
            atual.completion_tokens, novo.completion_tokens
        ),
        total_tokens=_somar_token(atual.total_tokens, novo.total_tokens),
    )


def _somar_token(a: int | None, b: int | None) -> int | None:
    if a is None and b is None:
        return None
    return (a or 0) + (b or 0)


def _data(iso: str):
    return datetime.fromisoformat(iso).date()


async def _exigir_pessoa(banco: Banco, pessoa_id: str) -> None:
    if await banco.obter_pessoa(pessoa_id) is None:
        raise HTTPException(status_code=404, detail="pessoa não encontrada")
