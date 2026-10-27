from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

import httpx
from fastapi import HTTPException

from .config import Config

logger = logging.getLogger(__name__)


class Conflito(Exception):
    """Violação de unicidade (equivalente ao IntegrityError do SQLite)."""


class ErroBanco(Exception):
    def __init__(self, detalhe: str, *, status: int | None = None) -> None:
        super().__init__(detalhe)
        self.detalhe = detalhe
        self.status = status


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class BancoSupabase:
    """Acesso ao Postgres via PostgREST usando o JWT do próprio usuário.

    O RLS vale porque cada request fala com o PostgREST como `authenticated`
    e com o `sub` do token; a API nunca usa service_role no caminho de chat.
    """

    def __init__(self, config: Config, token: str) -> None:
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

    async def criar_conversa(self, pessoa_id: str) -> dict:
        dados = await self._req(
            "POST",
            "conversas",
            corpo={"pessoa_id": pessoa_id},
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
    ) -> dict:
        dados = await self._req(
            "POST",
            "mensagens",
            corpo={
                "conversa_id": conversa_id,
                "papel": papel,
                "conteudo": conteudo,
                "status": status,
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
                "select": "id,papel,conteudo,status,criada_em",
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
