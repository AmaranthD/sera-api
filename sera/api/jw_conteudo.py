from __future__ import annotations

import re
import time
import unicodedata
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
_cacho: dict[tuple[str, str], tuple[float, "ConteudoJW"]] = {}


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
            if tag in {"div", "article"} and atributos.get("id") == "article":
                self.em_artigo = True
                self.profundidade = 1
            return

        if tag in {"div", "article"}:
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
        if tag in {"div", "article"}:
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


def _sem_acentos(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(
        caractere
        for caractere in decomposto
        if not unicodedata.combining(caractere)
    )


_LIVROS_PT = {
    "genesis": 1, "gen": 1, "gn": 1,
    "exodo": 2, "exo": 2, "ex": 2,
    "levitico": 3, "lev": 3, "lv": 3,
    "numeros": 4, "num": 4, "nm": 4,
    "deuteronomio": 5, "deut": 5, "dt": 5, "de": 5,
    "josue": 6, "jos": 6,
    "juizes": 7, "jz": 7,
    "rute": 8, "rt": 8,
    "1 samuel": 9, "1samuel": 9, "1sa": 9, "1 sam": 9, "1 sa": 9,
    "2 samuel": 10, "2samuel": 10, "2sa": 10, "2 sam": 10, "2 sa": 10,
    "1 reis": 11, "1reis": 11, "1re": 11, "1 re": 11,
    "2 reis": 12, "2reis": 12, "2re": 12, "2 re": 12,
    "1 cronicas": 13, "1cronicas": 13, "1cr": 13, "1 cr": 13,
    "2 cronicas": 14, "2cronicas": 14, "2cr": 14, "2 cr": 14,
    "esdras": 15, "esd": 15,
    "neemias": 16, "nee": 16, "ne": 16,
    "ester": 17, "est": 17,
    "job": 18,
    "salmo": 19, "salmos": 19, "sal": 19, "sl": 19,
    "proverbios": 20, "prov": 20, "pr": 20,
    "eclesiastes": 21, "ecl": 21, "ec": 21,
    "canticos": 22, "cant": 22, "ca": 22,
    "isaias": 23, "isa": 23, "is": 23,
    "jeremias": 24, "jer": 24, "je": 24,
    "lamentacoes": 25, "lam": 25, "la": 25,
    "ezequiel": 26, "eze": 26, "ez": 26,
    "daniel": 27, "dan": 27, "da": 27,
    "oseias": 28, "ose": 28, "os": 28,
    "joel": 29, "jl": 29,
    "amos": 30, "am": 30,
    "obadias": 31, "oba": 31, "ob": 31,
    "jonas": 32, "jon": 32,
    "miqueias": 33, "miq": 33, "mq": 33, "mi": 33,
    "naum": 34, "na": 34,
    "habacuque": 35, "hab": 35,
    "sofonias": 36, "sof": 36,
    "ageu": 37, "age": 37, "ag": 37,
    "zacarias": 38, "zac": 38, "za": 38,
    "malaquias": 39, "mal": 39, "ml": 39,
    "mateus": 40, "mat": 40, "mt": 40,
    "marcos": 41, "mar": 41, "mc": 41,
    "lucas": 42, "luc": 42, "lc": 42, "lu": 42,
    "joao": 43, "jo": 43,
    "atos": 44, "at": 44,
    "romanos": 45, "rom": 45, "ro": 45,
    "1 corintios": 46, "1corintios": 46, "1co": 46, "1 co": 46,
    "2 corintios": 47, "2corintios": 47, "2co": 47, "2 co": 47,
    "galatas": 48, "gal": 48, "ga": 48,
    "efesios": 49, "ef": 49,
    "filipenses": 50, "fil": 50, "fl": 50,
    "colossenses": 51, "col": 51,
    "1 tessalonicenses": 52, "1tessalonicenses": 52, "1te": 52, "1 te": 52,
    "2 tessalonicenses": 53, "2tessalonicenses": 53, "2te": 53, "2 te": 53,
    "1 timoteo": 54, "1timoteo": 54, "1ti": 54, "1 ti": 54,
    "2 timoteo": 55, "2timoteo": 55, "2ti": 55, "2 ti": 55,
    "tito": 56, "tit": 56, "tt": 56,
    "filemom": 57, "filem": 57, "fm": 57,
    "hebreus": 58, "heb": 58, "he": 58,
    "tiago": 59, "tia": 59, "tg": 59,
    "1 pedro": 60, "1pedro": 60, "1pe": 60, "1 pe": 60,
    "2 pedro": 61, "2pedro": 61, "2pe": 61, "2 pe": 61,
    "1 joao": 62, "1joao": 62, "1jo": 62, "1 jo": 62,
    "2 joao": 63, "2joao": 63, "2jo": 63, "2 jo": 63,
    "3 joao": 64, "3joao": 64, "3jo": 64, "3 jo": 64,
    "judas": 65, "jud": 65,
    "apocalipse": 66, "apo": 66, "ap": 66, "rev": 66,
}

_ALIAS_BIBLIA = "|".join(
    re.escape(alias)
    for alias in sorted(_LIVROS_PT, key=len, reverse=True)
)

_REFERENCIA = re.compile(
    rf"^({_ALIAS_BIBLIA})\s*(\d{{1,3}})"
    r"(?::\s*(\d{1,3})(?:\s*-\s*(\d{1,3}))?)?$"
)


def _limpar_referencia(texto: str) -> str:
    texto = re.sub(r"[*_`]", "", texto or "")
    texto = re.sub(r"[()\[\]]", " ", texto)
    texto = texto.replace("–", "-")
    texto = re.sub(r"\.", "", texto)
    return re.sub(r"\s+", " ", texto).strip(" .,;:").lower()


def parse_referencia_biblica(
    texto: str,
) -> tuple[int | None, int | None, int | None, int | None] | None:
    """Interpreta 'Atos 20:35', 'Fil. 1:1' ou '19:17'.

    Devolve `(livro, capítulo, versículo, fim)`. Sem livro, o capítulo vem
    da própria página (útil para referências encadeadas como '19:17').
    """
    bruto = _limpar_referencia(texto)
    if not bruto:
        return None
    if bruto == "jó" or bruto.startswith("jó "):
        bruto = "job" + bruto[2:]
    sem = _sem_acentos(bruto)

    achado = re.fullmatch(
        r"(\d{1,3}):(\d{1,3})(?:\s*-\s*(\d{1,3}))?", sem
    )
    if achado:
        inicio = int(achado.group(2))
        fim = int(achado.group(3)) if achado.group(3) else None
        if fim is not None and fim < inicio:
            fim = None
        return None, int(achado.group(1)), inicio, fim

    achado = re.fullmatch(r"(\d{1,3})(?:\s*-\s*(\d{1,3}))?", sem)
    if achado:
        inicio = int(achado.group(1))
        fim = int(achado.group(2)) if achado.group(2) else None
        if fim is not None and fim < inicio:
            fim = None
        return None, None, inicio, fim

    achado = _REFERENCIA.match(sem)
    if not achado:
        return None
    inicio = int(achado.group(3)) if achado.group(3) else None
    fim = int(achado.group(4)) if achado.group(4) else None
    if fim is not None and inicio is not None and fim < inicio:
        fim = None
    return (
        _LIVROS_PT[achado.group(1)],
        int(achado.group(2)),
        inicio,
        fim,
    )


class _ExtratorBiblia(HTMLParser):
    """Coleta os versículos de uma página bíblica do WOL.

    Os versículos ficam em spans `id="v44-20-35-1"`; cada sufixo pode ser
    um pedaço do mesmo versículo. O parser junta os pedaços e preserva a
    ordem, sem trazer as notas de estudo nem as referências cruzadas.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.em_artigo = False
        self.profundidade = 0
        self.capturando: tuple[int, int, int] | None = None
        self.span_profundidade = 0
        self.buf: list[str] = []
        self.versos: dict[tuple[int, int, int], list[str]] = {}
        self.ordem: list[tuple[int, int, int]] = []
        self.capitulo: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        atributos = dict(attrs)
        if not self.em_artigo:
            if tag in {"div", "article"} and atributos.get("id") == "article":
                self.em_artigo = True
                self.profundidade = 1
            return
        if tag in {"div", "article"}:
            self.profundidade += 1
        if tag != "span":
            return
        if self.capturando is not None:
            self.span_profundidade += 1
            return
        achado = re.match(
            r"v(\d+)-(\d+)-(\d+)-(\d+)", atributos.get("id") or ""
        )
        if not achado:
            return
        chave = (
            int(achado.group(1)),
            int(achado.group(2)),
            int(achado.group(3)),
        )
        self.capturando = chave
        self.span_profundidade = 1
        self.buf = []
        if self.capitulo is None:
            self.capitulo = chave[1]
        if chave not in self.versos:
            self.versos[chave] = []
            self.ordem.append(chave)

    def handle_endtag(self, tag: str) -> None:
        if not self.em_artigo:
            return
        if tag in {"div", "article"}:
            self.profundidade -= 1
            if self.profundidade <= 0:
                self._despejar()
                self.em_artigo = False
                self.capturando = None
            return
        if tag == "span" and self.capturando is not None:
            self.span_profundidade -= 1
            if self.span_profundidade <= 0:
                self._despejar()
                self.capturando = None

    def handle_data(self, data: str) -> None:
        if self.em_artigo and self.capturando is not None:
            self.buf.append(data)

    def _despejar(self) -> None:
        if self.capturando is None:
            return
        texto = " ".join("".join(self.buf).split())
        self.buf.clear()
        if not texto:
            return
        texto = re.sub(r"\s*\+\s*", " ", texto)
        texto = re.sub(r"\s*\*\s*", " ", texto)
        texto = " ".join(texto.split())
        if texto:
            self.versos.setdefault(self.capturando, []).append(texto)


def _titulo_biblia(
    nome_pagina: str,
    capitulo: int | None,
    inicio: int | None,
    fim: int | None,
) -> str:
    base = re.sub(
        r"\s+\d+(?::\d+)?(?:-\d+)?\s*$", "", nome_pagina
    ).strip() or nome_pagina
    if capitulo is None:
        return nome_pagina
    if inicio is None:
        return f"{base} {capitulo}"
    if fim is not None and fim != inicio:
        return f"{base} {capitulo}:{inicio}-{fim}"
    return f"{base} {capitulo}:{inicio}"


def extrair_biblia(
    html: str, url: str, referencia: str | None = None
) -> ConteudoJW:
    """Mostra só o versículo (ou o capítulo) da página bíblica."""
    extrator = _ExtratorBiblia()
    extrator.feed(html)
    extrator.close()
    if not extrator.versos:
        raise ConteudoJWIndisponivel("a página não tem versículos legíveis")

    nome_pagina = _limpar_titulo(html)
    referencia_lida = parse_referencia_biblica(referencia or "")
    capitulo = extrator.capitulo
    selecionados = list(extrator.ordem)
    titulo = nome_pagina

    if referencia_lida is not None:
        _livro, capitulo_ref, inicio, fim = referencia_lida
        if capitulo_ref is not None:
            capitulo = capitulo_ref
        if inicio is None:
            filtrados = [chave for chave in extrator.ordem if chave[1] == capitulo]
        else:
            limite = fim if fim is not None else inicio
            filtrados = [
                chave
                for chave in extrator.ordem
                if chave[1] == capitulo and inicio <= chave[2] <= limite
            ]
        if filtrados:
            selecionados = filtrados
            titulo = _titulo_biblia(nome_pagina, capitulo, inicio, fim)

    paragrafos = [
        " ".join(extrator.versos[chave])
        for chave in selecionados
        if extrator.versos.get(chave)
    ]
    if not paragrafos:
        raise ConteudoJWIndisponivel("o versículo não foi encontrado")
    return ConteudoJW(
        titulo=titulo,
        paragrafos=_limitar(paragrafos),
        url=url,
    )


def _eh_link_biblia(url: str) -> bool:
    return "/wol/bc/" in url or "/wol/b/" in url


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
    referencia: str | None = None,
    transporte: httpx.AsyncBaseTransport | None = None,
    timeout: float = 20.0,
) -> ConteudoJW:
    destino = normalizar_url_jw(url)
    chave_cache = (destino, " ".join((referencia or "").split()).lower())
    agora = time.monotonic()
    guardado = _cacho.get(chave_cache)
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
    if _eh_link_biblia(destino):
        try:
            conteudo = extrair_biblia(
                resposta.text, destino, referencia
            )
        except ConteudoJWIndisponivel:
            conteudo = extrair_conteudo_jw(resposta.text, destino)
    else:
        conteudo = extrair_conteudo_jw(resposta.text, destino)

    if len(_cacho) >= _CACHE_MAX:
        _cacho.clear()
    _cacho[chave_cache] = (agora, conteudo)
    return conteudo
