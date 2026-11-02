from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

import httpx
from fastapi import HTTPException

from .config import Config
from .tempo import agora_iso as agora

logger = logging.getLogger(__name__)


class Conflito(Exception):
    """Violação de unicidade (equivalente ao IntegrityError do SQLite)."""


class ErroBanco(Exception):
    def __init__(self, detalhe: str, *, status: int | None = None) -> None:
        super().__init__(detalhe)
        self.detalhe = detalhe
        self.status = status


class BancoSupabase:
    """Acesso ao Postgres via PostgREST usando o JWT do próprio usuário.

    O RLS vale porque cada request fala com o PostgREST como `authenticated`
    e com o `sub` do token; a API nunca usa service_role no caminho de chat.
    """

    def __init__(
        self,
        config: Config,
        token: str,
        *,
        transporte: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not config.supabase_url or not config.supabase_anon_key:
            raise ValueError("Supabase não configurado")
        if not token:
            raise ValueError("token do usuário é obrigatório")

        base = config.supabase_url.rstrip("/")
        self._http = httpx.AsyncClient(
            base_url=f"{base}/rest/v1/",
            timeout=httpx.Timeout(20.0, connect=10.0),
            headers={
                "apikey": config.supabase_anon_key,
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            transport=transporte,
        )

    async def fechar(self) -> None:
        await self._http.aclose()

    async def _req(
        self,
        metodo: str,
        caminho: str,
        *,
        params: Mapping[str, str] | None = None,
        corpo: Any = None,
        prefer: str | None = None,
    ) -> Any:
        cabecalhos = {"Prefer": prefer} if prefer else None
        try:
            resposta = await self._http.request(
                metodo,
                caminho.lstrip("/"),
                params=params,
                json=corpo,
                headers=cabecalhos,
            )
        except httpx.HTTPError as erro:
            logger.warning("falha ao falar com o PostgREST: %s", erro)
            raise ErroBanco("banco indisponível") from erro

        if resposta.status_code == 401:
            raise HTTPException(
                status_code=401,
                detail="sessão expirada",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if resposta.status_code == 409 or "23505" in resposta.text:
            raise Conflito(resposta.text[:300])
        if resposta.status_code >= 400:
            logger.warning(
                "PostgREST %s em %s: %s",
                resposta.status_code,
                caminho,
                resposta.text[:300],
            )
            raise ErroBanco(
                f"PostgREST {resposta.status_code}: {resposta.text[:300]}",
                status=resposta.status_code,
            )
        if resposta.status_code == 204 or not resposta.content:
            return None
        return resposta.json()

    async def criar_pessoa(
        self,
        pessoa_id: str,
        nome: str,
        faixa_etaria: str,
        perfil: str,
        acesso_vault: bool = True,
    ) -> dict:
        dados = await self._req(
            "POST",
            "pessoas",
            corpo={
                "id": pessoa_id,
                "nome": nome,
                "faixa_etaria": faixa_etaria,
                "perfil": perfil,
                "acesso_vault": acesso_vault,
            },
            prefer="return=representation",
        )
        return _um(dados)

    async def obter_pessoa(self, pessoa_id: str) -> dict | None:
        dados = await self._req(
            "GET",
            "pessoas",
            params={"select": "*", "id": f"eq.{pessoa_id}"},
        )
        return _primeiro(dados)

    async def listar_pessoas(self) -> list[dict]:
        return await self._req(
            "GET",
            "pessoas",
            params={"select": "*", "order": "nome.asc"},
        )

    async def apagar_pessoa(self, pessoa_id: str) -> bool:
        dados = await self._req(
            "DELETE",
            "pessoas",
            params={"id": f"eq.{pessoa_id}"},
            prefer="return=representation",
        )
        return bool(dados)

    async def criar_conversa(
        self, pessoa_id: str, titulo: str | None = None
    ) -> dict:
        dados = await self._req(
            "POST",
            "conversas",
            corpo={"pessoa_id": pessoa_id, "titulo": titulo},
            prefer="return=representation",
        )
        return _um(dados)

    async def obter_conversa(self, conversa_id: str) -> dict | None:
        dados = await self._req(
            "GET",
            "conversas",
            params={"select": "*", "id": f"eq.{conversa_id}"},
        )
        return _primeiro(dados)

    async def listar_conversas(self, pessoa_id: str) -> list[dict]:
        return await self._req(
            "GET",
            "conversas",
            params={
                "select": "*",
                "pessoa_id": f"eq.{pessoa_id}",
                "order": "atualizada_em.desc",
            },
        )

    async def criar_mensagem(
        self,
        conversa_id: str,
        papel: str,
        conteudo: str,
        status: str = "completa",
        fontes: Sequence[dict] | None = None,
    ) -> dict:
        dados = await self._req(
            "POST",
            "mensagens",
            corpo={
                "conversa_id": conversa_id,
                "papel": papel,
                "conteudo": conteudo,
                "status": status,
                "fontes": list(fontes or []),
            },
            prefer="return=representation",
        )
        mensagem = _um(dados)
        await self._req(
            "PATCH",
            "conversas",
            params={"id": f"eq.{conversa_id}"},
            corpo={"atualizada_em": agora()},
            prefer="return=minimal",
        )
        return mensagem

    async def atualizar_mensagem(
        self,
        mensagem_id: str,
        conteudo: str,
        status: str,
        fontes: Sequence[dict] | None = None,
    ) -> dict | None:
        corpo: dict = {"conteudo": conteudo, "status": status}
        if fontes is not None:
            corpo["fontes"] = list(fontes)
        dados = await self._req(
            "PATCH",
            "mensagens",
            params={"id": f"eq.{mensagem_id}"},
            corpo=corpo,
            prefer="return=representation",
        )
        return _um(dados) if dados else None

    async def obter_mensagem(self, mensagem_id: str) -> dict | None:
        dados = await self._req(
            "GET",
            "mensagens",
            params={"select": "*", "id": f"eq.{mensagem_id}"},
        )
        return _primeiro(dados)

    async def mensagem_gerando(self, conversa_id: str) -> dict | None:
        dados = await self._req(
            "GET",
            "mensagens",
            params={
                "select": "*",
                "conversa_id": f"eq.{conversa_id}",
                "status": "eq.gerando",
                "order": "criada_em.asc",
                "limit": "1",
            },
        )
        return _primeiro(dados)

    async def marcar_gerando_interrompidas(
        self, conversa_id: str, segundos: int = 600
    ) -> None:
        limite = (
            datetime.now(timezone.utc) - timedelta(seconds=segundos)
        ).isoformat(timespec="seconds")
        await self._req(
            "PATCH",
            "mensagens",
            params={
                "conversa_id": f"eq.{conversa_id}",
                "status": "eq.gerando",
                "criada_em": f"lt.{limite}",
            },
            corpo={"status": "interrompida"},
            prefer="return=minimal",
        )

    async def ultimas_mensagens(
        self, conversa_id: str, limite: int
    ) -> list[dict]:
        dados = await self._req(
            "GET",
            "mensagens",
            params={
                "select": "id,papel,conteudo,status,criada_em",
                "conversa_id": f"eq.{conversa_id}",
                "status": "eq.completa",
                "order": "criada_em.desc",
                "limit": str(limite),
            },
        )
        return list(reversed(dados or []))

    async def listar_mensagens(self, conversa_id: str) -> list[dict]:
        return await self._req(
            "GET",
            "mensagens",
            params={
                "select": "id,conversa_id,papel,conteudo,status,fontes,criada_em",
                "conversa_id": f"eq.{conversa_id}",
                "order": "criada_em.asc",
            },
        )

    async def criar_memoria(
        self, pessoa_id: str, texto: str, categoria: str
    ) -> dict:
        dados = await self._req(
            "POST",
            "memorias",
            corpo={
                "pessoa_id": pessoa_id,
                "texto": texto,
                "categoria": categoria,
            },
            prefer="return=representation",
        )
        return _um(dados)

    async def listar_memorias(self, pessoa_id: str) -> list[dict]:
        return await self._req(
            "GET",
            "memorias",
            params={
                "select": "*",
                "pessoa_id": f"eq.{pessoa_id}",
                "order": "criada_em.asc",
            },
        )

    async def apagar_memoria(self, pessoa_id: str, memoria_id: str) -> bool:
        dados = await self._req(
            "DELETE",
            "memorias",
            params={
                "id": f"eq.{memoria_id}",
                "pessoa_id": f"eq.{pessoa_id}",
            },
            prefer="return=representation",
        )
        return bool(dados)

    async def atualizar_memoria(
        self,
        pessoa_id: str,
        memoria_id: str,
        texto: str,
        categoria: str,
    ) -> dict | None:
        dados = await self._req(
            "PATCH",
            "memorias",
            params={
                "id": f"eq.{memoria_id}",
                "pessoa_id": f"eq.{pessoa_id}",
            },
            corpo={"texto": texto, "categoria": categoria},
            prefer="return=representation",
        )
        return _primeiro(dados)

    async def adicionar_tema(self, pessoa_id: str, tema: str) -> bool:
        try:
            await self._req(
                "POST",
                "nao_mencionar",
                corpo={"pessoa_id": pessoa_id, "tema": tema},
                prefer="return=minimal",
            )
        except Conflito:
            return False
        return True

    async def listar_temas(self, pessoa_id: str) -> list[str]:
        dados = await self._req(
            "GET",
            "nao_mencionar",
            params={
                "select": "tema",
                "pessoa_id": f"eq.{pessoa_id}",
                "order": "tema.asc",
            },
        )
        return [linha["tema"] for linha in dados or []]

    async def remover_tema(self, pessoa_id: str, tema: str) -> bool:
        dados = await self._req(
            "DELETE",
            "nao_mencionar",
            params={
                "pessoa_id": f"eq.{pessoa_id}",
                "tema": f"eq.{tema}",
            },
            prefer="return=representation",
        )
        return bool(dados)

    async def criar_ajuste(
        self,
        pessoa_id: str,
        tipo: str,
        texto: str | None,
        valor: str | None,
        origem: str,
    ) -> dict:
        dados = await self._req(
            "POST",
            "ajustes",
            corpo={
                "pessoa_id": pessoa_id,
                "tipo": tipo,
                "texto": texto,
                "valor": valor,
                "origem": origem,
            },
            prefer="return=representation",
        )
        return _um(dados)

    async def listar_ajustes(self, pessoa_id: str) -> list[dict]:
        return await self._req(
            "GET",
            "ajustes",
            params={
                "select": "*",
                "pessoa_id": f"eq.{pessoa_id}",
                "order": "criada_em.asc",
            },
        )

    async def apagar_ajuste(self, pessoa_id: str, ajuste_id: str) -> bool:
        dados = await self._req(
            "DELETE",
            "ajustes",
            params={
                "id": f"eq.{ajuste_id}",
                "pessoa_id": f"eq.{pessoa_id}",
            },
            prefer="return=representation",
        )
        return bool(dados)

    async def atualizar_ajuste(
        self,
        pessoa_id: str,
        ajuste_id: str,
        texto: str | None,
        valor: str | None,
    ) -> dict | None:
        dados = await self._req(
            "PATCH",
            "ajustes",
            params={
                "id": f"eq.{ajuste_id}",
                "pessoa_id": f"eq.{pessoa_id}",
            },
            corpo={"texto": texto, "valor": valor},
            prefer="return=representation",
        )
        return _primeiro(dados)

    async def criar_compromisso(
        self, pessoa_id: str, dados: dict
    ) -> dict:
        momento = agora()
        resultado = await self._req(
            "POST",
            "compromissos",
            corpo={
                "pessoa_id": pessoa_id,
                "titulo": dados["titulo"],
                "descricao": dados.get("descricao") or "",
                "inicio": dados["inicio"],
                "fim": dados["fim"],
                "fuso": dados["fuso"],
                "lembrete_minutos": dados["lembrete_minutos"],
                "lembrete_em": dados["lembrete_em"],
                "criado_em": momento,
                "atualizado_em": momento,
            },
            prefer="return=representation",
        )
        return _um(resultado)

    async def listar_compromissos(
        self,
        pessoa_id: str,
        de: str | None = None,
        ate: str | None = None,
    ) -> list[dict]:
        params = {
            "select": "*",
            "pessoa_id": f"eq.{pessoa_id}",
            "order": "inicio.asc",
        }
        if de is not None:
            params["fim"] = f"gt.{de}"
        if ate is not None:
            params["inicio"] = f"lt.{ate}"
        return await self._req("GET", "compromissos", params=params) or []

    async def obter_compromisso(self, compromisso_id: str) -> dict | None:
        dados = await self._req(
            "GET",
            "compromissos",
            params={"select": "*", "id": f"eq.{compromisso_id}"},
        )
        return _primeiro(dados)

    async def atualizar_compromisso(
        self, compromisso_id: str, dados: dict
    ) -> dict | None:
        atual = await self.obter_compromisso(compromisso_id)
        if atual is None:
            return None
        enviado = (
            None
            if atual.get("lembrete_em") != dados["lembrete_em"]
            else atual.get("lembrete_enviado_em")
        )
        resultado = await self._req(
            "PATCH",
            "compromissos",
            params={"id": f"eq.{compromisso_id}"},
            corpo={
                "titulo": dados["titulo"],
                "descricao": dados.get("descricao") or "",
                "inicio": dados["inicio"],
                "fim": dados["fim"],
                "fuso": dados["fuso"],
                "lembrete_minutos": dados["lembrete_minutos"],
                "lembrete_em": dados["lembrete_em"],
                "lembrete_enviado_em": enviado,
                "atualizado_em": agora(),
            },
            prefer="return=representation",
        )
        return _um(resultado) if resultado else None

    async def apagar_compromisso(self, compromisso_id: str) -> bool:
        dados = await self._req(
            "DELETE",
            "compromissos",
            params={"id": f"eq.{compromisso_id}"},
            prefer="return=representation",
        )
        return bool(dados)

    async def conflito_compromisso(
        self,
        pessoa_id: str,
        inicio: str,
        fim: str,
        excluir_id: str | None = None,
    ) -> dict | None:
        params = {
            "select": "*",
            "pessoa_id": f"eq.{pessoa_id}",
            "inicio": f"lt.{fim}",
            "fim": f"gt.{inicio}",
            "order": "inicio.asc",
            "limit": "1",
        }
        if excluir_id is not None:
            params["id"] = f"neq.{excluir_id}"
        dados = await self._req("GET", "compromissos", params=params)
        return _primeiro(dados)

    async def lembretes_pendentes(self, momento: str) -> list[dict]:
        return await self._req(
            "GET",
            "compromissos",
            params={
                "select": "*",
                "lembrete_enviado_em": "is.null",
                "lembrete_em": f"lte.{momento}",
                "fim": f"gte.{momento}",
                "order": "lembrete_em.asc",
                "limit": "200",
            },
        ) or []

    async def reivindicar_lembrete(
        self, compromisso_id: str, momento: str
    ) -> bool:
        dados = await self._req(
            "PATCH",
            "compromissos",
            params={
                "id": f"eq.{compromisso_id}",
                "lembrete_enviado_em": "is.null",
            },
            corpo={"lembrete_enviado_em": momento},
            prefer="return=representation",
        )
        return bool(dados)

    async def criar_inscricao(
        self,
        pessoa_id: str,
        endpoint: str,
        p256dh: str,
        auth: str,
        user_agent: str | None = None,
    ) -> dict:
        resultado = await self._req(
            "POST",
            "push_inscricoes",
            params={"on_conflict": "endpoint"},
            corpo={
                "pessoa_id": pessoa_id,
                "endpoint": endpoint,
                "p256dh": p256dh,
                "auth": auth,
                "user_agent": user_agent,
            },
            prefer="resolution=merge-duplicates,return=representation",
        )
        return _um(resultado)

    async def listar_inscricoes(self, pessoa_id: str) -> list[dict]:
        return await self._req(
            "GET",
            "push_inscricoes",
            params={
                "select": "*",
                "pessoa_id": f"eq.{pessoa_id}",
                "order": "criada_em.asc",
            },
        ) or []

    async def apagar_inscricao(
        self, pessoa_id: str, inscricao_id: str
    ) -> bool:
        dados = await self._req(
            "DELETE",
            "push_inscricoes",
            params={
                "id": f"eq.{inscricao_id}",
                "pessoa_id": f"eq.{pessoa_id}",
            },
            prefer="return=representation",
        )
        return bool(dados)

    async def apagar_inscricao_por_endpoint(self, endpoint: str) -> bool:
        dados = await self._req(
            "DELETE",
            "push_inscricoes",
            params={"endpoint": f"eq.{endpoint}"},
            prefer="return=representation",
        )
        return bool(dados)

    async def buscar_trechos(self, consulta: str, limite: int) -> list[dict]:
        if limite <= 0:
            return []
        dados = await self._req(
            "POST",
            "rpc/buscar_trechos",
            corpo={"consulta": consulta, "limite": limite},
        )
        return dados or []

    async def indexar_notas(self, notas: Sequence[Any]) -> dict:
        raise NotImplementedError(
            "indexação no Supabase usa service_role; rode o job de índice "
            "com a chave de serviço, fora da API"
        )

    async def estatisticas_indice(self) -> dict:
        raise NotImplementedError("indexação no Supabase é feita por job")

    async def limpar_indice(self) -> None:
        raise NotImplementedError("indexação no Supabase é feita por job")


def _primeiro(dados: Any) -> dict | None:
    if isinstance(dados, list):
        return dados[0] if dados else None
    if isinstance(dados, dict):
        return dados
    return None


def _um(dados: Any) -> dict:
    if isinstance(dados, list):
        if not dados:
            raise ErroBanco("operação não retornou linha (RLS ou conflito)")
        return dados[0]
    if isinstance(dados, dict):
        return dados
    raise ErroBanco("resposta inesperada do PostgREST")
