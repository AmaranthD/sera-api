from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx

from .config import Config

URL_TAVILY = "https://api.tavily.com/search"
_TAMANHO_MAXIMO_TRECHO = 500
_TAMANHO_MAXIMO_CONSULTA = 400
_MAXIMO_ENTRADAS_CACHE = 256

_PAISES_TAVILY = {
    "BR": "brazil",
    "PT": "portugal",
    "US": "united states",
    "AR": "argentina",
    "ES": "spain",
}


class BuscaIndisponivel(Exception):
    """A busca não pôde ser feita (rede, chave, limite, resposta inválida)."""

    def __init__(self, detalhe: str, *, status: int | None = None) -> None:
        super().__init__(detalhe)
        self.detalhe = detalhe
        self.status = status


@dataclass(frozen=True)
class ResultadoBusca:
    titulo: str
    url: str
    trecho: str
    data: str | None = None

    def como_dict(self) -> dict:
        dados = {"titulo": self.titulo, "url": self.url, "trecho": self.trecho}
        if self.data:
            dados["data"] = self.data
        return dados


class ClienteTavily:
    """Cliente mínimo da Tavily Search API, com cache em memória."""

    def __init__(
        self,
        config: Config,
        *,
        transporte: httpx.AsyncBaseTransport | None = None,
        relogio=time.monotonic,
    ) -> None:
        self._config = config
        self._transporte = transporte
        self._relogio = relogio
        self._cache: dict[str, tuple[float, tuple[ResultadoBusca, ...]]] = {}

    async def pesquisar(self, consulta: str) -> list[ResultadoBusca]:
        limpa = " ".join(str(consulta).split())[:_TAMANHO_MAXIMO_CONSULTA]
        if len(limpa) < 2:
            return []

        chave = limpa.casefold()
        agora = self._relogio()
        guardado = self._cache.get(chave)
        if guardado is not None and guardado[0] > agora:
            return list(guardado[1])

        resultados = await self._pedir(limpa)

        if self._config.busca_cache_ttl > 0 and resultados:
            if len(self._cache) >= _MAXIMO_ENTRADAS_CACHE:
                self._cache.clear()
            self._cache[chave] = (
                agora + self._config.busca_cache_ttl,
                tuple(resultados),
            )
        return resultados

    async def _pedir(self, consulta: str) -> list[ResultadoBusca]:
        chave = self._config.tavily_api_key
        if not chave:
            raise BuscaIndisponivel("TAVILY_API_KEY não configurada")

        payload: dict[str, Any] = {
            "query": consulta,
            "search_depth": "basic",
            "max_results": self._config.busca_max_resultados,
            "include_answer": False,
            "include_raw_content": False,
        }
        pais = _PAISES_TAVILY.get(self._config.busca_pais.strip().upper())
        if pais:
            payload["country"] = pais

        cabecalhos = {
            "Authorization": f"Bearer {chave}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        timeout = self._config.busca_timeout
        limites = httpx.Timeout(timeout, connect=min(5.0, timeout))

        try:
            async with httpx.AsyncClient(
                timeout=limites, transport=self._transporte
            ) as cliente:
                resposta = await cliente.post(
                    URL_TAVILY, json=payload, headers=cabecalhos
                )
        except httpx.TimeoutException as erro:
            raise BuscaIndisponivel(
                f"timeout ao consultar a Tavily: {erro}"
            ) from erro
        except httpx.RequestError as erro:
            raise BuscaIndisponivel(
                f"falha de rede ao consultar a Tavily: {erro}"
            ) from erro

        if resposta.status_code >= 400:
            corpo = resposta.text[:200]
            if resposta.status_code in (401, 403):
                detalhe = "chave da Tavily inválida ou sem permissão"
            elif resposta.status_code == 429:
                detalhe = "limite de buscas da Tavily atingido"
            elif resposta.status_code >= 500:
                detalhe = f"Tavily indisponível ({resposta.status_code})"
            else:
                detalhe = f"Tavily respondeu {resposta.status_code}: {corpo}"
            raise BuscaIndisponivel(detalhe, status=resposta.status_code)

        try:
            dados = resposta.json()
        except ValueError as erro:
            raise BuscaIndisponivel("Tavily devolveu JSON inválido") from erro
        if not isinstance(dados, Mapping):
            raise BuscaIndisponivel("Tavily devolveu uma resposta inesperada")

        return _normalizar(dados, self._config.busca_max_resultados)


def _normalizar(dados: Mapping, limite: int) -> list[ResultadoBusca]:
    brutos = dados.get("results")
    if not isinstance(brutos, list):
        return []

    vistos: set[str] = set()
    resultados: list[ResultadoBusca] = []
    for bruto in brutos:
        if not isinstance(bruto, Mapping):
            continue
        url = str(bruto.get("url") or "").strip()
        titulo = str(bruto.get("title") or "").strip()
        trecho = str(bruto.get("content") or "").strip()
        if not url or url in vistos:
            continue
        partes = urlparse(url)
        if partes.scheme not in ("http", "https") or not partes.netloc:
            continue
        vistos.add(url)
        data = bruto.get("published_date") or bruto.get("date")
        resultados.append(
            ResultadoBusca(
                titulo=titulo or url,
                url=url,
                trecho=trecho[:_TAMANHO_MAXIMO_TRECHO],
                data=str(data)[:40] if data else None,
            )
        )
        if len(resultados) >= limite:
            break
    return resultados
