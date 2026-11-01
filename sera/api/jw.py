from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import httpx

from .config import Config


class JWIndisponivel(Exception):
    """O serviço JW não respondeu ou devolveu erro."""

    def __init__(self, detalhe: str, *, status: int | None = None) -> None:
        super().__init__(detalhe)
        self.detalhe = detalhe
        self.status = status


@dataclass(frozen=True)
class RespostaJW:
    ferramenta: str
    texto: str
    erro: bool = False


class ClienteJW:
    """Cliente do facade REST do jw-mcp (serviço separado)."""

    def __init__(
        self,
        config: Config,
        *,
        transporte: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not config.jw_api_url or not config.jw_api_key:
            raise ValueError("JW_API_URL e JW_API_KEY são obrigatórias")
        self._config = config
        self._transporte = transporte
        self._url = f"{config.jw_api_url.rstrip('/')}/tool"

    async def executar(
        self,
        ferramenta: str,
        argumentos: Mapping[str, Any] | None = None,
    ) -> RespostaJW:
        payload = {
            "nome": ferramenta,
            "argumentos": dict(argumentos or {}),
        }
        cabecalhos = {
            "X-API-Key": self._config.jw_api_key or "",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        timeout = self._config.jw_timeout
        limites = httpx.Timeout(timeout, connect=min(8.0, timeout))

        try:
            async with httpx.AsyncClient(
                timeout=limites, transport=self._transporte
            ) as cliente:
                resposta = await cliente.post(
                    self._url, json=payload, headers=cabecalhos
                )
        except httpx.TimeoutException as erro:
            raise JWIndisponivel(
                f"timeout ao consultar o serviço JW: {erro}"
            ) from erro
        except httpx.RequestError as erro:
            raise JWIndisponivel(
                f"falha de rede ao consultar o serviço JW: {erro}"
            ) from erro

        if resposta.status_code >= 400:
            corpo = resposta.text[:240]
            if resposta.status_code == 401:
                detalhe = "chave da API JW inválida"
            elif resposta.status_code == 404:
                detalhe = f"ferramenta JW desconhecida: {ferramenta}"
            else:
                detalhe = f"serviço JW respondeu {resposta.status_code}: {corpo}"
            raise JWIndisponivel(detalhe, status=resposta.status_code)

        try:
            dados = resposta.json()
        except ValueError as erro:
            raise JWIndisponivel("serviço JW devolveu JSON inválido") from erro
        if not isinstance(dados, Mapping):
            raise JWIndisponivel("serviço JW devolveu uma resposta inesperada")

        resultado = dados.get("resultado")
        if not isinstance(resultado, Mapping):
            resultado = {}

        texto = _texto_do_resultado(resultado)
        if not texto:
            texto = "A ferramenta JW não retornou texto."

        limite = self._config.jw_max_chars
        if len(texto) > limite:
            texto = f"{texto[:limite].rstrip()}…"

        return RespostaJW(
            ferramenta=str(dados.get("ferramenta") or ferramenta),
            texto=texto,
            erro=bool(resultado.get("isError")),
        )


def _texto_do_resultado(resultado: Mapping) -> str:
    partes: list[str] = []
    conteudo = resultado.get("content")
    if isinstance(conteudo, list):
        for item in conteudo:
            if isinstance(item, Mapping) and item.get("type") == "text":
                texto = item.get("text")
                if isinstance(texto, str) and texto.strip():
                    partes.append(texto.strip())
    return "\n".join(partes)
