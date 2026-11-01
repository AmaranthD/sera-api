from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from dataclasses import dataclass
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
from .busca import BuscaIndisponivel, ClienteTavily, ResultadoBusca
from .config import Config
from .db import Banco
from .db_supabase import Conflito
from .ferramentas import (
    FERRAMENTAS,
    INSTRUCAO_BUSCA,
    FerramentaDesconhecida,
    FerramentaInvalida,
    bloco_resultados,
    consulta_explicita,
    executar_ferramenta,
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
from .schemas import (
    AjusteEntrada,
    ChatEntrada,
    MemoriaEntrada,
    PessoaEntrada,
    TemaEntrada,
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
        conversa = await banco.criar_conversa(
            pessoa_id, _titulo_da_mensagem(corpo.mensagem)
        )

    historico = await banco.ultimas_mensagens(
        conversa["id"], config.max_history_mensagens
    )
    _cortar_historico(historico, config.max_history_chars)

    mensagem_usuario = await banco.criar_mensagem(
        conversa["id"], "user", corpo.mensagem
    )

    system = await _montar_system(
        personality, linha_pessoa, banco, config, corpo.mensagem
    )
    busca, ferramentas, fontes, system = await _preparar_busca(
        request, config, corpo.mensagem, system
    )
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
            busca=busca,
            ferramentas=ferramentas,
        )

    return await _resposta_stream(
        request,
        banco,
        llm,
        config,
        conversa["id"],
        mensagem_usuario["id"],
        mensagens,
        busca=busca,
        ferramentas=ferramentas,
        fontes=fontes,
    )


async def _preparar_busca(
    request: Request,
    config: Config,
    mensagem: str,
    system: str,
) -> tuple[ClienteTavily | None, list[dict] | None, list[dict], str]:
    """Liga as ferramentas e, se o pedido for explícito, já busca antes.

    "Pesquise X" é interpretado como busca na internet sem depender de o
    modelo decidir chamar a ferramenta.
    """
    busca: ClienteTavily | None = getattr(request.app.state, "busca", None)
    if not config.busca_ativa or busca is None:
        return None, None, [], system

    fontes: list[dict] = []
    consulta = consulta_explicita(mensagem)

    if consulta is None:
        # O cliente Gemini desta camada ainda não executa tool calling.
        if config.llm_provider != "openai":
            return busca, None, fontes, system
        system = f"{system}\n\n{INSTRUCAO_BUSCA}"
        return busca, list(FERRAMENTAS), fontes, system

    try:
        resultados = await busca.pesquisar(consulta)
    except BuscaIndisponivel as erro:
        logger.warning("busca explícita falhou: %s", erro.detalhe)
        system = (
            f"{system}\n\n## Busca na internet\n"
            "A busca falhou agora. Responda sem inventar dados e avise que "
            "não conseguiu consultar a internet."
        )
        return busca, None, fontes, system

    fontes = [resultado.como_dict() for resultado in resultados]
    system = f"{system}\n\n{bloco_resultados(consulta, resultados)}"
    # A busca já foi feita: sem ferramentas nesta resposta para não repetir
    # consultas nem expor o loop de tool calling.
    return busca, None, fontes, system


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
    *,
    busca: ClienteTavily | None = None,
    ferramentas: list[dict] | None = None,
) -> dict:
    partes: list[str] = []
    uso: Uso | None = None
    try:
        async for evento in _fluxo_com_ferramentas(
            llm, mensagens, config, busca, ferramentas
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
    busca: ClienteTavily | None,
    ferramentas: list[dict] | None,
):
    """Executa o loop de tool calling e emite Delta/Fim e eventos de busca.

    Os resultados entram no system prompt em vez de virarem mensagens
    `assistant`/`tool`: alguns modelos (MiniMax via NVIDIA NIM) vazam a
    marcação interna de tool call quando relê esse protocolo. Assim o modelo
    vê apenas system/user e, na última rodada, responde sem ferramentas.
    """
    conversa = [dict(mensagem) for mensagem in mensagens]
    rodadas = config.busca_max_rodadas if busca is not None and ferramentas else 0
    chamadas: list[ChamadaFerramenta] = []

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

        if not chamadas or busca is None:
            return

        for chamada in chamadas:
            yield Pesquisando(_consulta_da_chamada(chamada))

        bloco, fontes = await _buscar_chamadas(chamadas, busca)
        if fontes:
            yield Fontes(tuple(fontes))
        if bloco:
            conversa[0]["content"] = (
                f"{conversa[0].get('content') or ''}\n\n{bloco}"
            )

    # Última rodada: sem ferramentas, para o modelo fechar a resposta com o
    # que já foi encontrado. Tirar a instrução de ferramentas do system evita
    # que o modelo tente chamar algo que não existe mais.
    conversa[0]["content"] = (
        f"{conversa[0].get('content') or ''}".replace(INSTRUCAO_BUSCA, "")
    ).strip()
    async for evento in llm.stream(
        conversa,
        temperatura=config.temperatura,
        max_tokens=config.max_tokens,
        ferramentas=None,
    ):
        if not isinstance(evento, Ferramenta):
            yield evento


async def _buscar_chamadas(
    chamadas: list[ChamadaFerramenta], busca: ClienteTavily
) -> tuple[str, list[dict]]:
    blocos: list[str] = []
    fontes: list[dict] = []
    vistos: set[str] = set()

    for chamada in chamadas:
        consulta = _consulta_da_chamada(chamada)
        try:
            resultado = await executar_ferramenta(
                chamada.nome, chamada.argumentos, busca
            )
        except (
            FerramentaDesconhecida,
            FerramentaInvalida,
            BuscaIndisponivel,
        ) as erro:
            logger.warning("ferramenta falhou: %s", erro)
            blocos.append(
                "## Busca na internet\n"
                f'A busca por "{consulta}" falhou: {erro}. '
                "Responda sem inventar dados e avise que não conseguiu "
                "consultar a internet."
            )
            continue

        itens = resultado.get("resultados") or []
        resultados = [ResultadoBusca(**item) for item in itens]
        blocos.append(
            bloco_resultados(resultado.get("consulta") or consulta, resultados)
        )
        for item in itens:
            url = item.get("url")
            if url and url not in vistos:
                vistos.add(url)
                fontes.append(item)

    return "\n\n".join(blocos), fontes


def _consulta_da_chamada(chamada: ChamadaFerramenta) -> str:
    try:
        dados = json.loads(chamada.argumentos or "{}")
    except json.JSONDecodeError:
        return ""
    if not isinstance(dados, dict):
        return ""
    return " ".join(str(dados.get("consulta") or "").split())


async def _resposta_stream(
    request: Request,
    banco: Banco,
    llm: ClienteLLM,
    config: Config,
    conversa_id: str,
    mensagem_usuario_id: str,
    mensagens: list[dict],
    *,
    busca: ClienteTavily | None = None,
    ferramentas: list[dict] | None = None,
    fontes: list[dict] | None = None,
) -> StreamingResponse:
    fluxo = _fluxo_com_ferramentas(llm, mensagens, config, busca, ferramentas)
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
