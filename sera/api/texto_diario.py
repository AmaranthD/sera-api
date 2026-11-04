from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, time as hora_do_dia, timezone
from html import unescape
from html.parser import HTMLParser
from typing import Any, Mapping
from urllib.parse import urljoin
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from .config import Config
from .jw_conteudo import normalizar_url_jw
from .webpush import (
    FalhaPush,
    NotificacoesIndisponiveis,
    enviar_push,
    payload_texto_diario,
)

logger = logging.getLogger(__name__)

URL_TEXTO_DIARIO = "https://wol.jw.org/pt/wol/dt/r5/lp-t/{ano}/{mes}/{dia}"
_BASE = "https://wol.jw.org"
_CACHE_TTL = 60 * 60
_CACHE_MAX = 10
_cache: dict[date, tuple[float, "TextoDoDia"]] = {}
_ultima_falha: dict[str, tuple[date, float]] = {}
_ESPERA_APOS_FALHA = 15 * 60


class TextoDiarioIndisponivel(Exception):
    """O texto diário ainda não está publicado ou o WOL não respondeu."""


@dataclass(frozen=True)
class TextoDoDia:
    dia: date
    titulo: str
    tema: str
    corpo: str
    url: str
    links: tuple[str, ...]


class _Markdown(HTMLParser):
    """Converte o HTML do texto diário em Markdown simples e seguro.

    Só `em`, `strong`, `a` e quebras de bloco sobrevivem. Links que não sejam
    do jw.org viram texto puro, para o front nunca receber um esquema
    inesperado.
    """

    def __init__(self, base: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base = base
        self.blocos: list[str] = []
        self.links: list[str] = []
        self._buf: list[str] = []
        self._abertos: list[tuple[str, str]] = []
        self._ignorar = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._ignorar += 1
            return
        if self._ignorar:
            return
        if tag == "a":
            href = dict(attrs).get("href") or ""
            destino = self._destino(href)
            if destino is None:
                self._abertos.append(("a", ""))
                return
            self.links.append(destino)
            self._buf.append("[")
            self._abertos.append(("a", destino))
        elif tag in {"em", "i"}:
            self._buf.append("*")
            self._abertos.append(("em", ""))
        elif tag in {"strong", "b"}:
            self._buf.append("**")
            self._abertos.append(("strong", ""))
        elif tag == "br":
            self._buf.append(" ")
        elif tag in {"p", "div", "blockquote", "li"}:
            self._despejar()

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            if self._ignorar:
                self._ignorar -= 1
            return
        if self._ignorar:
            return
        if tag in {"p", "div", "blockquote", "li"}:
            self._despejar()
            return
        for indice in range(len(self._abertos) - 1, -1, -1):
            nome, destino = self._abertos[indice]
            if nome != tag:
                continue
            self._abertos.pop(indice)
            if tag == "a" and destino:
                self._buf.append(f"]({destino})")
            elif tag == "em":
                self._buf.append("*")
            elif tag == "strong":
                self._buf.append("**")
            return

    def handle_data(self, data: str) -> None:
        if not self._ignorar:
            self._buf.append(data)

    def _destino(self, href: str) -> str | None:
        if not href or href.startswith("#"):
            return None
        try:
            return normalizar_url_jw(urljoin(self.base, href))
        except Exception:
            return None

    def _despejar(self) -> None:
        texto = " ".join("".join(self._buf).split())
        self._buf.clear()
        if not texto:
            return
        texto = re.sub(r"\*\s*([.,;:!?])\s*\*", r"\1", texto)
        texto = re.sub(r"\s+([.,;:!?])", r"\1", texto)
        if texto and texto not in self.blocos:
            self.blocos.append(texto)

    def close(self) -> None:
        super().close()
        self._despejar()


def _sem_tags(html: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def _fragmento(html: str) -> str:
    tema = html.find("themeScrp")
    if tema < 0:
        raise TextoDiarioIndisponivel("texto diário ainda não publicado")
    inicio = html.rfind('<div class="itemData', 0, tema)
    if inicio < 0:
        inicio = max(0, tema - 4000)
    fim = html.find('<div class="todayItem', tema)
    if fim < 0:
        fim = html.find('<div class="itemData', tema + 1)
    if fim < 0:
        fim = len(html)
    return html[inicio:fim]


def _tema_do_fragmento(fragmento: str) -> str:
    achado = re.search(
        r'<p[^>]*class="[^"]*themeScrp[^"]*"[^>]*>([\s\S]*?)</p>',
        fragmento,
        re.IGNORECASE,
    )
    if not achado:
        raise TextoDiarioIndisponivel("texto diário sem versículo-tema")
    return achado.group(1)


def _corpo_do_fragmento(fragmento: str) -> str:
    achado = re.search(
        r'<div[^>]*class="[^"]*bodyTxt[^"]*"[^>]*>([\s\S]*?)</div>',
        fragmento,
        re.IGNORECASE,
    )
    return achado.group(1) if achado else ""


def _titulo_do_fragmento(fragmento: str, dia: date) -> str:
    achado = re.search(
        r"<header[^>]*>[\s\S]*?<h2[^>]*>([\s\S]*?)</h2>",
        fragmento,
        re.IGNORECASE,
    )
    if achado:
        titulo = _sem_tags(achado.group(1))
        if titulo:
            return titulo
    return dia.strftime("%d/%m/%Y")


def extrair_texto_do_dia(
    html: str, *, dia: date, url: str
) -> TextoDoDia:
    """Interpreta a página diária do WOL. Levanta erro se não publicado."""
    fragmento = _fragmento(html)
    tema_parser = _Markdown(_BASE)
    tema_parser.feed(_tema_do_fragmento(fragmento))
    tema_parser.close()

    corpo_parser = _Markdown(_BASE)
    corpo_parser.feed(_corpo_do_fragmento(fragmento))
    corpo_parser.close()

    tema = "\n\n".join(tema_parser.blocos).strip()
    if not tema.strip("* "):
        raise TextoDiarioIndisponivel("texto diário sem versículo-tema")

    links = tuple(dict.fromkeys((*tema_parser.links, *corpo_parser.links)))
    return TextoDoDia(
        dia=dia,
        titulo=_titulo_do_fragmento(fragmento, dia),
        tema=tema,
        corpo="\n\n".join(corpo_parser.blocos).strip(),
        url=url,
        links=links,
    )


async def buscar_texto_do_dia(
    dia: date | None = None,
    *,
    transporte: httpx.AsyncBaseTransport | None = None,
    timeout: float = 20.0,
) -> TextoDoDia:
    dia = dia or date.today()
    agora = time.monotonic()
    guardado = _cache.get(dia)
    if guardado is not None and agora - guardado[0] < _CACHE_TTL:
        return guardado[1]

    url = URL_TEXTO_DIARIO.format(ano=dia.year, mes=dia.month, dia=dia.day)
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
            resposta = await cliente.get(url)
    except httpx.TimeoutException as erro:
        raise TextoDiarioIndisponivel(
            "o jw.org demorou para responder"
        ) from erro
    except httpx.RequestError as erro:
        raise TextoDiarioIndisponivel(
            f"não foi possível consultar o jw.org: {erro}"
        ) from erro

    if resposta.status_code >= 400:
        raise TextoDiarioIndisponivel(
            f"o jw.org respondeu {resposta.status_code} para o texto do dia"
        )

    texto = extrair_texto_do_dia(resposta.text, dia=dia, url=url)
    if len(_cache) >= _CACHE_MAX:
        _cache.clear()
    _cache[dia] = (agora, texto)
    return texto


def formatar_texto_do_dia(texto: TextoDoDia) -> str:
    partes = [
        f"## Texto diário — {texto.titulo}",
        f"> {texto.tema}",
    ]
    if texto.corpo:
        partes.append(texto.corpo)
    partes.append(f"---\n[Ver no JW.org]({texto.url}#externo)")
    return "\n\n".join(partes)


def _zona(nome: str | None, padrao: str) -> ZoneInfo:
    try:
        return ZoneInfo(nome or padrao)
    except (ValueError, ZoneInfoNotFoundError):
        return ZoneInfo(padrao)


def _dia_local(momento: datetime, fuso: str) -> date:
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    try:
        zona = ZoneInfo(fuso)
    except (ValueError, ZoneInfoNotFoundError):
        zona = timezone.utc
    return momento.astimezone(zona).date()


async def _notificar_texto(
    banco: Any,
    config: Config,
    pessoa_id: str,
    conversa_id: str,
    texto: TextoDoDia,
) -> tuple[int, int]:
    if not config.notificacoes_ativas:
        return 0, 0
    try:
        inscricoes = await banco.listar_inscricoes(pessoa_id)
    except Exception:
        logger.exception("falha ao listar inscrições do texto diário")
        return 0, 0

    payload = payload_texto_diario(conversa_id, texto)
    enviados = 0
    falhas = 0
    for inscricao in inscricoes:
        try:
            await enviar_push(inscricao, payload, config)
            enviados += 1
        except FalhaPush as erro:
            falhas += 1
            if erro.inscricao_morta:
                await banco.apagar_inscricao_por_endpoint(
                    inscricao["endpoint"]
                )
        except NotificacoesIndisponiveis as erro:
            logger.warning("push do texto diário indisponível: %s", erro)
            break
        except Exception:
            falhas += 1
            logger.exception("falha ao notificar texto diário")
    return enviados, falhas


async def entregar_texto_do_dia(
    banco: Any,
    config: Config,
    pessoa_id: str,
    *,
    conversa_id: str | None = None,
    dia: date | None = None,
    fuso: str | None = None,
    transporte: httpx.AsyncBaseTransport | None = None,
) -> dict:
    """Busca, posta na conversa dedicada e notifica. Determinístico."""
    if dia is None:
        dia = _dia_local(datetime.now(timezone.utc), fuso or config.fuso_horario)
    texto = await buscar_texto_do_dia(dia, transporte=transporte)

    if conversa_id:
        conversa = await banco.obter_conversa(conversa_id)
        if conversa is None or conversa.get("pessoa_id") != pessoa_id:
            conversa_id = None
    if not conversa_id:
        conversa = await banco.criar_conversa(pessoa_id, "Texto diário")
        conversa_id = conversa["id"]
        definir = getattr(banco, "definir_conversa_texto_diario", None)
        if callable(definir):
            await definir(pessoa_id, conversa_id)

    conteudo = formatar_texto_do_dia(texto)
    mensagem = await banco.criar_mensagem(
        conversa_id, "assistant", conteudo, "completa"
    )
    enviados, falhas = await _notificar_texto(
        banco, config, pessoa_id, conversa_id, texto
    )
    return {
        "conversa_id": conversa_id,
        "mensagem_id": mensagem["id"],
        "dia": texto.dia.isoformat(),
        "enviados": enviados,
        "falhas": falhas,
    }


async def disparar_textos_diarios(
    banco: Any,
    config: Config,
    momento: datetime | None = None,
    *,
    transporte: httpx.AsyncBaseTransport | None = None,
) -> dict:
    """Entrega o texto do dia para quem já passou do horário escolhido.

    A reivindicação do dia acontece antes da busca, então duas instâncias
    não entregam duas vezes. Em caso de falha, a reivindicação é liberada e
    a pessoa tenta de novo depois de um intervalo (evita martelar o WOL).
    """
    instante = momento or datetime.now(timezone.utc)
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=timezone.utc)

    assinaturas = await banco.listar_assinaturas_texto_diario()
    enviados = 0
    falhas = 0
    agora_mono = time.monotonic()

    for assinatura in assinaturas:
        if not assinatura.get("ativo"):
            continue
        pessoa_id = assinatura["pessoa_id"]
        fuso = assinatura.get("fuso") or config.fuso_horario
        local = instante.astimezone(_zona(fuso, config.fuso_horario))
        dia = local.date()

        try:
            hora = hora_do_dia.fromisoformat(assinatura.get("hora") or "07:00")
        except ValueError:
            logger.warning(
                "horário inválido no texto diário de %s: %r",
                pessoa_id,
                assinatura.get("hora"),
            )
            continue
        if local.hour < hora.hour or (
            local.hour == hora.hour and local.minute < hora.minute
        ):
            continue

        chave_dia = dia.isoformat()
        if assinatura.get("ultimo_envio_dia") == chave_dia:
            continue
        ultima = _ultima_falha.get(pessoa_id)
        if (
            ultima is not None
            and ultima[0] == dia
            and agora_mono - ultima[1] < _ESPERA_APOS_FALHA
        ):
            continue

        if not await banco.reivindicar_texto_diario(pessoa_id, chave_dia):
            continue

        try:
            resultado = await entregar_texto_do_dia(
                banco,
                config,
                pessoa_id,
                conversa_id=assinatura.get("conversa_id"),
                dia=dia,
                fuso=fuso,
                transporte=transporte,
            )
        except Exception:
            await banco.liberar_texto_diario(pessoa_id, chave_dia)
            _ultima_falha[pessoa_id] = (dia, agora_mono)
            falhas += 1
            logger.exception(
                "falha ao entregar o texto diário de %s", pessoa_id
            )
        else:
            _ultima_falha.pop(pessoa_id, None)
            enviados += 1
            logger.info(
                "texto diário entregue: pessoa=%s conversa=%s dia=%s",
                pessoa_id,
                resultado["conversa_id"],
                resultado["dia"],
            )

    return {
        "assinaturas": len(assinaturas),
        "enviados": enviados,
        "falhas": falhas,
    }


def limpar_cache() -> None:
    """Usado nos testes para não reaproveitar conteúdo entre casos."""
    _cache.clear()
    _ultima_falha.clear()
