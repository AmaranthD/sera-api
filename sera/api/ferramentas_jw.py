from __future__ import annotations

import copy
import json
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from .ferramentas_base import (
    ContextoFerramentas,
    FerramentaInvalida,
    NOME_JW,
    _normalizar_texto,
)

_ARGUMENTOS_JW = {
    "search_bible_books": ("query",),
    "get_bible_verse": ("book", "chapter", "verse"),
    "get_verse_with_study": ("book", "chapter", "verse", "fields", "limit"),
    "get_bible_verse_url": ("book", "chapter", "verse"),
    "getWorkbookLinks": ("pub", "langwritten", "issue", "fileformat"),
    "getWorkbookContent": ("url",),
    "getWatchtowerLinks": ("pub", "langwritten", "issue", "fileformat"),
    "getWatchtowerContent": ("url",),
    "get_jw_captions": ("video_id",),
}


ESQUEMA_JW = {
    "type": "function",
    "function": {
        "name": NOME_JW,
        "description": (
            "Consulta a Bíblia e publicações das Testemunhas de Jeová: "
            "versículos, notas de estudo, apostila (CLM), A Sentinela e "
            "legendas de vídeos. Use quando a pessoa pedir conteúdo bíblico "
            "ou de estudo. No modo JW esta é a única fonte: se não houver "
            "ferramenta para o tema exato, escolha o relato ou versículo "
            "mais próximo e busque o texto real antes de responder."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ferramenta": {
                    "type": "string",
                    "enum": [
                        "search_bible_books",
                        "get_bible_verse",
                        "get_verse_with_study",
                        "get_bible_verse_url",
                        "getWorkbookLinks",
                        "getWorkbookContent",
                        "getWatchtowerLinks",
                        "getWatchtowerContent",
                        "get_jw_captions",
                    ],
                },
                "query": {
                    "type": "string",
                    "description": (
                        "Nome do livro para search_bible_books. Ex.: "
                        '"matthew", "psalms", "joão".'
                    ),
                },
                "book": {
                    "type": "integer",
                    "description": (
                        "Número do livro de 1 a 66. Use search_bible_books "
                        "antes se não souber. Ex.: Salmos=19, Mateus=40."
                    ),
                },
                "chapter": {"type": "integer"},
                "verse": {
                    "type": "string",
                    "description": (
                        "Para get_bible_verse: um único número ('7'). Para "
                        "get_verse_with_study: número ou faixa ('3-5'). Para "
                        "get_bible_verse_url: número, faixa ('3-5') ou lista "
                        "('1,3,5')."
                    ),
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Campos de get_verse_with_study. Ex.: "
                        '["verses","study_notes","study_articles"].'
                    ),
                },
                "limit": {"type": "integer"},
                "url": {
                    "type": "string",
                    "description": (
                        "URL retornada por getWorkbookLinks ou "
                        "getWatchtowerLinks."
                    ),
                },
                "video_id": {"type": "string"},
                "pub": {
                    "type": "string",
                    "description": "'mwb' para apostila, 'w' para Sentinela.",
                },
                "langwritten": {
                    "type": "string",
                    "description": "'T' para português, 'E' para inglês.",
                },
                "issue": {
                    "type": "string",
                    "description": "Opcional, formato YYYYMM00.",
                },
                "fileformat": {"type": "string"},
            },
            "required": ["ferramenta"],
        },
    },
}


INSTRUCAO_JW = """\
## Conteúdo JW

Você pode consultar a Bíblia e publicações com a ferramenta `jw`.

- Use quando a pessoa pedir versículo, estudo bíblico, apostila (CLM),
  A Sentinela, vídeo ou conteúdo das Testemunhas de Jeová.
- Ferramentas e argumentos (todos vão no mesmo objeto, com `ferramenta`):
  - `search_bible_books`: `ferramenta=search_bible_books`, `query=matthew`;
    use antes para descobrir o número do livro (1–66).
  - `get_bible_verse`: `ferramenta=get_bible_verse`, `book=43`,
    `chapter=3`, `verse=16` — um versículo só.
  - `get_verse_with_study`: `ferramenta=get_verse_with_study`, `book=40`,
    `chapter=5`, `verse=3-5`, `fields=[verses, study_notes,
    study_articles]` — use esta para faixas.
  - `get_bible_verse_url`: `ferramenta=get_bible_verse_url`, `book=19`,
    `chapter=23`, `verse=1`.
  - `getWorkbookLinks`: `ferramenta=getWorkbookLinks`, `langwritten=T` —
    primeiro passo da apostila.
  - `getWorkbookContent`: `ferramenta=getWorkbookContent`, `url=...` — use
    uma URL retornada por `getWorkbookLinks`.
  - `getWatchtowerLinks`: `ferramenta=getWatchtowerLinks`, `langwritten=T`
    — primeiro passo d'A Sentinela.
  - `getWatchtowerContent`: `ferramenta=getWatchtowerContent`, `url=...` —
    use uma URL retornada por `getWatchtowerLinks`.
  - `get_jw_captions`: `ferramenta=get_jw_captions`, `video_id=...`.
- Não invente texto bíblico nem conteúdo de publicação. Se a ferramenta não
  trouxer, diga que não encontrou.
- Cite a URL quando o resultado tiver uma.
"""


INSTRUCAO_JW_MODO = """\
## Modo JW (fonte única)

A pessoa ativou o modo JW nesta resposta. A única fonte de verdade é a
ferramenta `jw`.

- Consulte a ferramenta `jw` antes de responder qualquer coisa sobre Bíblia,
  estudo, apostila (CLM), A Sentinela ou vídeos. Se a pessoa escrever
  "pesquise", "busque", "procure" ou "consulte", a pesquisa é nas
  publicações JW — não na internet.
- Não use a busca na internet nem responda de memória citando texto bíblico
  ou de publicação. Se a ferramenta não devolver o texto, diga que não
  encontrou em vez de completar por conta própria.
- Se o tema exato não existir no material consultado, traga o relato,
  princípio ou cenário mais próximo do que a ferramenta devolveu e deixe
  claro que é o mais próximo encontrado, não o tema exato.
- Sempre que citar um versículo, chame também `get_bible_verse_url` para
  obter o link do texto em jw.org.
- Se o texto vier em inglês (o acervo do serviço é majoritariamente em
  inglês), traduza a citação para português e diga que foi traduzida,
  mantendo o link original.
- Escreva a resposta inteira em português do Brasil; não deixe termos ou
  frases em inglês nem caracteres de outros idiomas no meio do texto.
- Termine sempre com uma seção `## Fontes` com **um único link em
  Markdown**: o da página principal consultada (o versículo em jw.org ou a
  publicação). Não liste artigos de estudo, notas, referências cruzadas nem
  links internos que apareçam no material.
"""


async def _jw(
    dados: Mapping, contexto: ContextoFerramentas
) -> dict:
    if contexto.jw is None:
        raise FerramentaInvalida("o conteúdo JW está desligado")

    ferramenta = str(dados.get("ferramenta") or "").strip()
    if not ferramenta:
        raise FerramentaInvalida("informe qual ferramenta JW usar")
    if ferramenta not in _ARGUMENTOS_JW:
        raise FerramentaInvalida(f"ferramenta JW desconhecida: {ferramenta}")

    aninhados = dados.get("argumentos")
    if isinstance(aninhados, Mapping):
        # Compatibilidade com o formato antigo {"argumentos": {...}}.
        argumentos = dict(aninhados)
    elif aninhados is not None:
        raise FerramentaInvalida(
            "os argumentos da ferramenta JW precisam ser um objeto"
        )
    else:
        argumentos = {
            campo: dados[campo]
            for campo in _ARGUMENTOS_JW[ferramenta]
            if dados.get(campo) is not None
        }
    argumentos = _normalizar_argumentos_jw(ferramenta, argumentos)

    resposta = await contexto.jw.executar(ferramenta, argumentos)
    texto = formatar_resultado_jw(resposta.ferramenta, resposta.texto)
    limite = getattr(contexto.jw, "max_chars", None)
    if isinstance(limite, int) and limite > 0 and len(texto) > limite:
        texto = f"{texto[:limite].rstrip()}…"

    return {
        "ferramenta": resposta.ferramenta,
        "texto": texto,
        "erro": resposta.erro,
        "fontes": fontes_jw(ferramenta, argumentos, resposta.texto),
    }


_URL_REGEX = re.compile(r"https?://[^\s<>\"'()\[\]{}]+")


_HOSTS_JW = ("jw.org", "jw-cdn.org")


_MAX_FONTES_JW = 8


_TITULO_FONTE_JW = {
    "search_bible_books": "JW · livros da Bíblia",
    "get_bible_verse": "JW · versículo",
    "get_verse_with_study": "JW · versículo com notas de estudo",
    "get_bible_verse_url": "JW · Bíblia",
    "getWorkbookLinks": "JW · apostila (CLM)",
    "getWorkbookContent": "JW · apostila (CLM)",
    "getWatchtowerLinks": "JW · A Sentinela",
    "getWatchtowerContent": "JW · A Sentinela",
    "get_jw_captions": "JW · legendas de vídeo",
}


def extrair_urls_jw(texto: str) -> list[str]:
    """URLs de jw.org/jw-cdn.org citadas no retorno de uma ferramenta JW."""
    urls: list[str] = []
    for bruto in _URL_REGEX.findall(texto or ""):
        url = bruto.rstrip(".,;:!?")
        try:
            host = (urlparse(url).hostname or "").lower()
        except ValueError:
            continue
        if not any(
            host == host_jw or host.endswith(f".{host_jw}")
            for host_jw in _HOSTS_JW
        ):
            continue
        if url not in urls:
            urls.append(url)
        if len(urls) >= _MAX_FONTES_JW:
            break
    return urls


def titulo_fonte_jw(ferramenta: str) -> str:
    return _TITULO_FONTE_JW.get(ferramenta, "JW")


_FERRAMENTAS_BIBLIA = (
    "search_bible_books",
    "get_bible_verse",
    "get_verse_with_study",
    "get_bible_verse_url",
)


_TERMOS_APOSTILA = ("apostila", "clm", "mwb", "reuniao", "ministerio")


_TERMOS_SENTINELA = ("sentinela", "watchtower", "estudo da semana")


_TERMOS_VIDEO = ("video", "legenda", "cantico")


def ferramentas_jw_para(mensagem: str) -> list[str]:
    """Ferramentas JW que fazem sentido para a mensagem.

    Sem palavras-chave de publicação, ficam só as ferramentas bíblicas. Isso
    evita o modelo gastar rodadas com a apostila quando a pessoa só quer um
    texto ou um princípio sobre um tema.
    """
    texto = _normalizar_texto(mensagem)
    permitidas = list(_FERRAMENTAS_BIBLIA)
    if any(termo in texto for termo in _TERMOS_APOSTILA):
        permitidas.extend(("getWorkbookLinks", "getWorkbookContent"))
    if any(termo in texto for termo in _TERMOS_SENTINELA):
        permitidas.extend(("getWatchtowerLinks", "getWatchtowerContent"))
    if any(termo in texto for termo in _TERMOS_VIDEO):
        permitidas.append("get_jw_captions")
    return permitidas


def _esquema_jw(permitidas: Sequence[str] | None = None) -> dict:
    if not permitidas:
        return ESQUEMA_JW
    esquema = copy.deepcopy(ESQUEMA_JW)
    enum = esquema["function"]["parameters"]["properties"]["ferramenta"]["enum"]
    enum[:] = [nome for nome in enum if nome in permitidas]
    return esquema


def _inteiro(valor: Any) -> Any:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return valor


def _normalizar_argumentos_jw(
    ferramenta: str, argumentos: Mapping
) -> dict:
    """Corrige tipos que o scraper do jw-mcp não aceita.

    O `get_bible_verse` compara `verse_num === verse`, então precisa de um
    inteiro; e só entende um versículo por vez. O `get_verse_with_study`
    entende número ou faixa, mas não lista com vírgulas.
    """
    dados = dict(argumentos)
    for campo in ("book", "chapter", "limit"):
        if campo in dados:
            dados[campo] = _inteiro(dados[campo])

    verso = dados.get("verse")
    if verso is None:
        return dados
    texto = str(verso).strip()

    if ferramenta == "get_bible_verse":
        primeiro = re.match(r"\d+", texto)
        if primeiro:
            dados["verse"] = int(primeiro.group(0))
    elif ferramenta == "get_verse_with_study":
        if "-" not in texto and "," in texto:
            numeros = [int(numero) for numero in re.findall(r"\d+", texto)]
            if numeros:
                dados["verse"] = f"{min(numeros)}-{max(numeros)}"
    return dados


def _url_biblia(
    book: Any, chapter: Any, verse: Any = None
) -> str | None:
    """Monta o link do texto em jw.org (locale português)."""
    try:
        livro = int(book)
        capitulo = int(chapter)
    except (TypeError, ValueError):
        return None

    parametro = f"{livro}{capitulo:03d}"
    if verse not in (None, ""):
        texto = str(verse).strip()
        if "-" in texto:
            inicio, _, fim = texto.partition("-")
            try:
                parametro += (
                    f"{int(inicio):03d}-{livro}{capitulo:03d}{int(fim):03d}"
                )
            except ValueError:
                return None
        else:
            try:
                parametro += f"{int(texto.split(',')[0]):03d}"
            except ValueError:
                return None

    return (
        "https://www.jw.org/finder?wtlocale=T&prefer=lang"
        f"&bible={parametro}&pub=nwtsty"
    )


def fontes_jw(
    ferramenta: str, argumentos: Mapping, texto: str
) -> list[dict]:
    """Uma fonte principal por consulta, não todos os links internos."""
    if ferramenta in (
        "get_bible_verse",
        "get_verse_with_study",
        "get_bible_verse_url",
    ):
        if ferramenta == "get_bible_verse_url":
            urls = extrair_urls_jw(texto)
            if urls:
                return [{"titulo": "Bíblia (jw.org)", "url": urls[0]}]
        url = _url_biblia(
            argumentos.get("book"),
            argumentos.get("chapter"),
            argumentos.get("verse"),
        )
        return [{"titulo": "Bíblia (jw.org)", "url": url}] if url else []

    if ferramenta in ("getWorkbookContent", "getWatchtowerContent"):
        url = str(argumentos.get("url") or "").strip()
        if not url:
            return []
        titulo = (
            "Apostila (CLM)"
            if ferramenta == "getWorkbookContent"
            else "A Sentinela"
        )
        return [{"titulo": titulo, "url": url}]

    if ferramenta == "get_jw_captions":
        urls = extrair_urls_jw(texto)
        return [{"titulo": "Vídeo (jw.org)", "url": urls[0]}] if urls else []

    # search_bible_books e os *Links são etapas de descoberta, não a fonte.
    return []


def formatar_resultado_jw(ferramenta: str, texto: str) -> str:
    """Transforma o JSON do jw-mcp em texto legível para o modelo.

    Sem isso o modelo recebe JSON cru, às vezes repete chaves/campos na
    resposta e cita todos os links internos (artigos de estudo) como fontes.
    """
    try:
        dados = json.loads(texto)
    except (json.JSONDecodeError, TypeError):
        return texto
    if not isinstance(dados, dict):
        return texto

    linhas: list[str] = []

    if ferramenta == "search_bible_books":
        for livro in dados.get("books") or []:
            if isinstance(livro, Mapping):
                linhas.append(
                    f"- {livro.get('name')} (livro {livro.get('number')})"
                )
    elif ferramenta in (
        "get_bible_verse",
        "get_verse_with_study",
        "get_bible_verse_url",
    ):
        referencia = dados.get("reference")
        if referencia:
            linhas.append(f"Referência: {referencia}")
        if dados.get("text"):
            linhas.append(str(dados["text"]))
        for verso in dados.get("verses") or []:
            if isinstance(verso, Mapping):
                linhas.append(
                    f"{verso.get('verse_num')}. {verso.get('verse_text')}"
                )
        if dados.get("combined_text"):
            linhas.append(str(dados["combined_text"]))

        notas = dados.get("study_notes")
        if isinstance(notas, Mapping) and notas:
            linhas.append("")
            linhas.append("Notas de estudo:")
            for verso, nota in notas.items():
                linhas.append(f"- v. {verso}: {nota}")

        artigos = dados.get("study_articles")
        if isinstance(artigos, list) and artigos:
            linhas.append("")
            linhas.append("Artigos relacionados:")
            for artigo in artigos:
                if isinstance(artigo, Mapping) and artigo.get("title"):
                    linhas.append(f"- {artigo['title']}")

        cruzadas = dados.get("cross_references")
        if isinstance(cruzadas, list) and cruzadas:
            linhas.append("")
            linhas.append("Referências cruzadas: " + "; ".join(
                str(item) for item in cruzadas
            ))
    elif ferramenta in ("getWorkbookLinks", "getWatchtowerLinks"):
        if dados.get("pubName"):
            linhas.append(f"Publicação: {dados['pubName']}")
        if dados.get("formattedDate"):
            linhas.append(f"Edição: {dados['formattedDate']}")
        itens = dados.get("weekFiles") or dados.get("articles") or []
        for item in itens:
            if isinstance(item, Mapping) and item.get("title"):
                linhas.append(f"- {item['title']}")
    elif ferramenta in ("getWorkbookContent", "getWatchtowerContent"):
        if dados.get("parsedText"):
            linhas.append(str(dados["parsedText"]))
    else:
        return texto

    return "\n".join(linhas) if linhas else texto


_LIVROS_BIBLIA = {
    "genesis": 1,
    "exodo": 2,
    "levitico": 3,
    "numeros": 4,
    "deuteronomio": 5,
    "josue": 6,
    "juizes": 7,
    "rute": 8,
    "1 samuel": 9,
    "1samuel": 9,
    "2 samuel": 10,
    "2samuel": 10,
    "1 reis": 11,
    "1reis": 11,
    "2 reis": 12,
    "2reis": 12,
    "1 cronicas": 13,
    "1cronicas": 13,
    "2 cronicas": 14,
    "2cronicas": 14,
    "esdras": 15,
    "neemias": 16,
    "ester": 17,
    "salmo": 19,
    "salmos": 19,
    "sl": 19,
    "proverbios": 20,
    "eclesiastes": 21,
    "canticos": 22,
    "isaias": 23,
    "jeremias": 24,
    "lamentacoes": 25,
    "ezequiel": 26,
    "daniel": 27,
    "oseias": 28,
    "joel": 29,
    "amos": 30,
    "obadias": 31,
    "jonas": 32,
    "miqueias": 33,
    "naum": 34,
    "habacuque": 35,
    "sofonias": 36,
    "ageu": 37,
    "zacarias": 38,
    "malaquias": 39,
    "mateus": 40,
    "mt": 40,
    "marcos": 41,
    "mc": 41,
    "lucas": 42,
    "lc": 42,
    "joao": 43,
    "atos": 44,
    "at": 44,
    "romanos": 45,
    "rom": 45,
    "1 corintios": 46,
    "1corintios": 46,
    "2 corintios": 47,
    "2corintios": 47,
    "galatas": 48,
    "efesios": 49,
    "filipenses": 50,
    "colossenses": 51,
    "1 tessalonicenses": 52,
    "1tessalonicenses": 52,
    "2 tessalonicenses": 53,
    "2tessalonicenses": 53,
    "1 timoteo": 54,
    "1timoteo": 54,
    "2 timoteo": 55,
    "2timoteo": 55,
    "tito": 56,
    "filemom": 57,
    "hebreus": 58,
    "tiago": 59,
    "1 pedro": 60,
    "1pedro": 60,
    "2 pedro": 61,
    "2pedro": 61,
    "1 joao": 62,
    "1joao": 62,
    "2 joao": 63,
    "2joao": 63,
    "3 joao": 64,
    "3joao": 64,
    "judas": 65,
    "apocalipse": 66,
}


_ALIAS_BIBLIA = "|".join(
    re.escape(alias)
    for alias in sorted(_LIVROS_BIBLIA, key=len, reverse=True)
)


_REFERENCIA_BIBLICA = re.compile(
    rf"\b({_ALIAS_BIBLIA})\s*(\d{{1,3}})\s*[:.]\s*(\d{{1,3}})"
    r"(?:\s*[-–]\s*(\d{1,3}))?"
)


def referencia_biblica(
    mensagem: str,
) -> tuple[int, int, int, int | None] | None:
    """Extrai (livro, capítulo, versículo, fim) de "1 Pedro 5:7"."""
    texto = _normalizar_texto(mensagem)
    achado = _REFERENCIA_BIBLICA.search(texto)
    if achado is None:
        return None

    livro = _LIVROS_BIBLIA[achado.group(1)]
    capitulo = int(achado.group(2))
    inicio = int(achado.group(3))
    fim = int(achado.group(4)) if achado.group(4) else None
    if fim is not None and fim < inicio:
        fim = None
    return livro, capitulo, inicio, fim
