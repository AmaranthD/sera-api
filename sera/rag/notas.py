from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

import yaml

DIRETORIOS_IGNORADOS = (".obsidian", ".trash", "Templates")

_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
_TITULO = re.compile(r"\A#[ \t]+(.+?)[ \t]*\Z")
_SECAO = re.compile(r"\A##[ \t]+(.+?)[ \t]*\Z")
_PALAVRA = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+")

_PALAVRAS_VAZIAS = frozenset(
    """
    a as ao aos aquela aquele aquilo as com como da das de dela dele deles
    demais depois do dos e ela elas ele eles em entre era essa esse esta
    este eu foi foram há isso isto já mais mas me mesmo meu minha muito na
    nas não nem no nos num numa o os ou para pela pelas pelo pelos por qual
    quais quando que quem se sem seu sua também tem ter teu tua um uma você
    vocês
    """.split()
)


@dataclass(frozen=True)
class Secao:
    nome: str
    ordem: int
    texto: str


@dataclass(frozen=True)
class Nota:
    caminho: str
    titulo: str
    tags: tuple[str, ...]
    hash: str
    secoes: tuple[Secao, ...]

    @property
    def texto(self) -> str:
        return "\n\n".join(secao.texto for secao in self.secoes)


def ler_nota(caminho: str | Path, *, raiz: str | Path | None = None) -> Nota:
    caminho = Path(caminho)
    bruto = caminho.read_text(encoding="utf-8", errors="replace")
    relativo = (
        caminho.relative_to(Path(raiz)).as_posix() if raiz is not None else caminho.name
    )
    metadados, corpo = _separar_frontmatter(bruto)
    titulo, secoes = _extrair_titulo_e_secoes(corpo, caminho.stem)
    return Nota(
        caminho=relativo,
        titulo=titulo,
        tags=_normalizar_tags(metadados.get("tags")),
        hash=hashlib.sha256(bruto.encode("utf-8")).hexdigest(),
        secoes=secoes,
    )


def iterar_notas(
    raiz: str | Path, *, ignorar: Sequence[str] = DIRETORIOS_IGNORADOS
) -> Iterator[Nota]:
    raiz = Path(raiz)
    ignorados = {nome.casefold() for nome in ignorar}
    for caminho in sorted(raiz.rglob("*.md")):
        partes = caminho.relative_to(raiz).parts[:-1]
        if any(parte.casefold() in ignorados for parte in partes):
            continue
        yield ler_nota(caminho, raiz=raiz)


def termos_busca(texto: str, *, maximo: int = 24) -> list[str]:
    termos: list[str] = []
    vistos: set[str] = set()
    for bruto in _PALAVRA.findall(texto or ""):
        termo = bruto.casefold()
        if len(termo) < 3 or termo in vistos or termo in _PALAVRAS_VAZIAS:
            continue
        vistos.add(termo)
        termos.append(termo)
        if len(termos) >= maximo:
            break
    return termos


def expressao_fts(consulta: str) -> str:
    termos = termos_busca(consulta)
    if not termos:
        return ""
    return " OR ".join(f'"{termo}"' for termo in termos)


def _separar_frontmatter(bruto: str) -> tuple[dict, str]:
    encontrado = _FRONTMATTER.match(bruto)
    if not encontrado:
        return {}, bruto
    corpo = bruto[encontrado.end() :]
    try:
        dados = yaml.safe_load(encontrado.group(1))
    except yaml.YAMLError:
        dados = None
    return (dados if isinstance(dados, dict) else {}), corpo


def _extrair_titulo_e_secoes(
    corpo: str, padrao: str
) -> tuple[str, tuple[Secao, ...]]:
    titulo = ""
    secoes: list[Secao] = []
    nome = ""
    linhas: list[str] = []

    def fechar() -> None:
        texto = "\n".join(linhas).strip()
        if texto:
            secoes.append(Secao(nome=nome, ordem=len(secoes), texto=texto))

    for linha in corpo.splitlines():
        if not titulo:
            achado = _TITULO.match(linha)
            if achado:
                titulo = achado.group(1)
                continue
        achado_secao = _SECAO.match(linha)
        if achado_secao:
            fechar()
            nome = achado_secao.group(1)
            linhas = []
            continue
        linhas.append(linha)
    fechar()

    return titulo or padrao, tuple(secoes)


def _normalizar_tags(valor: object) -> tuple[str, ...]:
    if valor is None:
        return ()
    if isinstance(valor, str):
        brutos = re.split(r"[,\s]+", valor)
    elif isinstance(valor, (list, tuple, set)):
        brutos = [str(item) for item in valor]
    else:
        return ()
    tags: list[str] = []
    for bruto in brutos:
        tag = bruto.strip().lstrip("#").casefold()
        if tag and tag not in tags:
            tags.append(tag)
    return tuple(tags)
