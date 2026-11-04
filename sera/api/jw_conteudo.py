from __future__ import annotations

import re
import time
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urlparse, urlunparse

import httpx

_URL_JW = {"jw.org", "www.jw.org", "wol.jw.org"}
_CACHE_TTL = 6 * 60 * 60
_CACHE_MAX = 80
_LIMITE_CARACTERES = 14_000
_LIMITE_BLOCOS = 80
_cacho: dict[str, tuple[float, "ConteudoJW"]] = {}


class URLJWInvalida(Exception):
    """O link não aponta para uma página pública do jw.org."""


class ConteudoJWIndisponivel(Exception):
    """O jw.org não respondeu ou a página não tem conteúdo legível."""


@dataclass(frozen=True)
class ConteudoJW:
    titulo: str
    paragrafos: tuple[str, ...]
    url: str


def normalizar_url_jw(url: str) -> str:
    """Aceita só https/http de jw.org, sem portas alternativas (anti-SSRF)."""
    try:
        partes = urlparse((url or "").strip())
    except ValueError as erro:
        raise URLJWInvalida("link inválido") from erro
    host = (partes.hostname or "").lower()
    if partes.scheme not in {"http", "https"} or host not in _URL_JW:
        raise URLJWInvalida("só links do jw.org podem ser abertos")
    if partes.port not in (None, 80, 443):
        raise URLJWInvalida("porta não permitida")
    if not partes.path:
        raise URLJWInvalida("link sem caminho")
    return urlunparse(partes._replace(scheme="https", netloc=host))


class _ExtratorArtigo(HTMLParser):
    """Extrai título e parágrafos do bloco `#article` do WOL.

    Os blocos são delimitados por `p`, `li`, `blockquote` e títulos. O texto
    de navegação e scripts fica de fora. A intenção é alimentar um modal
    legível, não reproduzir a página inteira.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.em_artigo = False
        self.profundidade = 0
        self.titulo = ""
        self.blocos: list[str] = []
        self._buf: list[str] = []
        self._ignorar = 0
        self._heading = 0
        self._em_bloco = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        atributos = dict(attrs)
        if not self.em_artigo:
            if tag == "div" and atributos.get("id") == "article":
                self.em_artigo = True
                self.profundidade = 1
            return

        if tag == "div":
            self.profundidade += 1
        if tag in {"script", "style", "noscript"}:
            self._ignorar += 1
        if self._ignorar:
            return
        if tag in {"p", "li", "blockquote"}:
            self._despejar()
            self._em_bloco = True
        elif tag in {"h1", "h2", "h3"}:
            self._despejar()
            self._em_bloco = True
            self._heading = int(tag[1])
        elif tag == "br":
            self._buf.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if not self.em_artigo:
            return
        if tag == "div":
            self.profundidade -= 1
            if self.profundidade <= 0:
                self._despejar()
                self.em_artigo = False
                return
        if tag in {"script", "style", "noscript"} and self._ignorar:
            self._ignorar -= 1
        if self._ignorar:
            return
        if tag in {"p", "li", "blockquote", "h1", "h2", "h3"}:
            self._despejar()
            self._em_bloco = False
            self._heading = 0

    def handle_data(self, data: str) -> None:
        if self.em_artigo and not self._ignorar:
            self._buf.append(data)

    def _despejar(self) -> None:
        texto = " ".join("".join(self._buf).split())
        self._buf.clear()
        if not texto:
            return
        if self._heading and not self.titulo:
            self.titulo = texto
        if texto not in self.blocos:
            self.blocos.append(texto)

    def close(self) -> None:
        super().close()
        self._despejar()


_IGNORAR = {
    "Nenhum vídeo disponível para o trecho selecionado.",
    "Desculpe, ocorreu um erro ao carregar o vídeo.",
}


def _titulo_limpo(titulo: str) -> str:
    titulo = " ".join(titulo.split())
    titulo = re.sub(
        r"\s+[—–-]\s+BIBLIOTECA ON-LINE.*$", "", titulo, flags=re.IGNORECASE
    )
    return titulo or "JW.org"


def _limpar_titulo(html: str) -> str:
    achado = re.search(r"<title[^>]*>([\s\S]*?)</title>", html, re.IGNORECASE)
    if not achado:
        return "JW.org"
    titulo = re.sub(r"<[^>]+>", " ", unescape(achado.group(1)))
    return _titulo_limpo(titulo)


def _paragrafos_de_reserva(html: str) -> list[str]:
    """Fallback para páginas sem #article: só os <p> do documento."""
    blocos: list[str] = []
    for achado in re.finditer(r"<p[^>]*>([\s\S]*?)</p>", html, re.IGNORECASE):
        texto = re.sub(r"<[^>]+>", " ", achado.group(1))
        texto = " ".join(unescape(texto).split())
        if texto and texto not in blocos:
            blocos.append(texto)
    return blocos


def _limitar(blocos: Iterable[str]) -> tuple[str, ...]:
    saida: list[str] = []
    total = 0
    for bloco in blocos:
        if len(saida) >= _LIMITE_BLOCOS:
            break
        if total + len(bloco) > _LIMITE_CARACTERES:
            restante = _LIMITE_CARACTERES - total
            if restante > 80:
                saida.append(bloco[:restante].rstrip() + "…")
            break
        saida.append(bloco)
        total += len(bloco)
    return tuple(saida)


def extrair_conteudo_jw(html: str, url: str) -> ConteudoJW:
    extrator = _ExtratorArtigo()
    extrator.feed(html)
    extrator.close()

    titulo = _titulo_limpo(extrator.titulo or _limpar_titulo(html))
    blocos = [
        bloco
        for bloco in (list(extrator.blocos) or _paragrafos_de_reserva(html))
        if bloco not in _IGNORAR
    ]
    if not blocos:
        raise ConteudoJWIndisponivel("a página não tem texto para mostrar")

    if blocos and blocos[0] == titulo:
        blocos = blocos[1:]
    return ConteudoJW(
        titulo=titulo,
        paragrafos=_limitar(blocos),
        url=url,
    )


async def buscar_conteudo_jw(
    url: str,
    *,
    transporte: httpx.AsyncBaseTransport | None = None,
    timeout: float = 20.0,
) -> ConteudoJW:
    destino = normalizar_url_jw(url)
    agora = time.monotonic()
    guardado = _cacho.get(destino)
    if guardado is not None and agora - guardado[0] < _CACHE_TTL:
        return guardado[1]

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=min(8.0, timeout)),
            follow_redirects=True,
            transport=transporte,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; Sera/0.3; +https://jw.org) "
                    "AppleWebKit/537.36"
                ),
                "Accept-Language": "pt-BR,pt;q=0.9",
            },
        ) as cliente:
            resposta = await cliente.get(destino)
    except httpx.TimeoutException as erro:
        raise ConteudoJWIndisponivel(
            "o jw.org demorou para responder"
        ) from erro
    except httpx.RequestError as erro:
        raise ConteudoJWIndisponivel(
            f"não foi possível abrir o jw.org: {erro}"
        ) from erro

    if resposta.status_code >= 400:
        raise ConteudoJWIndisponivel(
            f"o jw.org respondeu {resposta.status_code}"
        )
    # Um redirecionamento não pode tirar a requisição do domínio do jw.org.
    normalizar_url_jw(str(resposta.url))
    conteudo = extrair_conteudo_jw(resposta.text, destino)

    if len(_cacho) >= _CACHE_MAX:
        _cacho.clear()
    _cacho[destino] = (agora, conteudo)
    return conteudo
