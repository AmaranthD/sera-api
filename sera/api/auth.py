from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
import jwt
from fastapi import HTTPException, Request

from .config import Config

logger = logging.getLogger(__name__)

_TTL_CACHE = 30.0
_TAMANHO_MAX_CACHE = 512


@dataclass(frozen=True)
class Usuario:
    id: str
    token: str
    email: str | None = None


class Autenticador(Protocol):
    async def validar(self, token: str) -> Usuario: ...


def _nao_autorizado(detalhe: str = "token inválido") -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=detalhe,
        headers={"WWW-Authenticate": "Bearer"},
    )


class AutenticadorSupabase:
    """Valida o access_token do Supabase.

    Tenta JWKS (JWT assimétrico) e cai para /auth/v1/user quando o projeto
    ainda assina com o segredo legado (HS256). A introspecção também cobre
    rotação de chaves sem precisar reiniciar a API.
    """

    def __init__(
        self,
        config: Config,
        *,
        cliente: httpx.AsyncClient | None = None,
    ) -> None:
        if not config.supabase_url or not config.supabase_anon_key:
            raise ValueError("Supabase não configurado")
        base = config.supabase_url.rstrip("/")
        self._config = config
        self._issuer = f"{base}/auth/v1"
        self._usuario_url = f"{self._issuer}/user"
        self._anon_key = config.supabase_anon_key
        self._jwks = jwt.PyJWKClient(
            f"{self._issuer}/.well-known/jwks.json",
            cache_keys=True,
            lifespan=300,
            timeout=10,
        )
        self._cliente = cliente
        self._cache: dict[str, tuple[Usuario, float]] = {}

    async def validar(self, token: str) -> Usuario:
        agora = time.monotonic()
        em_cache = self._cache.get(token)
        if em_cache and em_cache[1] > agora:
            return em_cache[0]

        usuario = await self._validar(token)
        if len(self._cache) >= _TAMANHO_MAX_CACHE:
            self._cache.clear()
        self._cache[token] = (usuario, agora + _TTL_CACHE)
        return usuario

    async def _validar(self, token: str) -> Usuario:
        claims = self._por_jwks(token)
        if claims is None:
            claims = await self._por_introspeccao(token)

        sub = claims.get("sub")
        if not sub:
            raise _nao_autorizado("token sem sub")
        email = claims.get("email")
        return Usuario(id=str(sub), token=token, email=email)

    def _por_jwks(self, token: str) -> dict[str, Any] | None:
        try:
            chave = self._jwks.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                chave.key,
                algorithms=["RS256", "ES256", "EdDSA"],
                audience=self._config.supabase_jwt_aud,
                issuer=self._issuer,
                options={"require": ["exp", "sub", "aud", "iss"]},
            )
        except (jwt.PyJWKClientError, jwt.InvalidTokenError):
            return None

    async def _por_introspeccao(self, token: str) -> dict[str, Any]:
        cabecalhos = {
            "apikey": self._anon_key,
            "Authorization": f"Bearer {token}",
        }
        try:
            if self._cliente is not None:
                resposta = await self._cliente.get(
                    self._usuario_url, headers=cabecalhos
                )
            else:
                async with httpx.AsyncClient(timeout=10.0) as cliente:
                    resposta = await cliente.get(
                        self._usuario_url, headers=cabecalhos
                    )
        except httpx.HTTPError as erro:
            logger.warning("falha ao validar token no Supabase: %s", erro)
            raise HTTPException(
                status_code=503, detail="autenticação indisponível"
            ) from erro

        if resposta.status_code == 401:
            raise _nao_autorizado()
        if resposta.status_code >= 400:
            logger.warning(
                "Supabase recusou a introspecção: %s %s",
                resposta.status_code,
                resposta.text[:200],
            )
            raise HTTPException(
                status_code=503, detail="autenticação indisponível"
            )

        dados = resposta.json()
        if not isinstance(dados, dict) or not dados.get("id"):
            raise _nao_autorizado()
        return {"sub": dados["id"], "email": dados.get("email")}

    async def fechar(self) -> None:
        if self._cliente is not None:
            await self._cliente.aclose()


async def usuario_atual(request: Request) -> Usuario | None:
    config: Config = request.app.state.config
    if not config.auth_required:
        return None

    autenticador: Autenticador | None = getattr(
        request.app.state, "autenticador", None
    )
    if autenticador is None:
        raise HTTPException(status_code=503, detail="autenticação indisponível")

    cabecalho = request.headers.get("authorization", "")
    esquema, _, token = cabecalho.partition(" ")
    token = token.strip()
    if esquema.lower() != "bearer" or not token:
        raise _nao_autorizado("Authorization Bearer ausente")

    return await autenticador.validar(token)
