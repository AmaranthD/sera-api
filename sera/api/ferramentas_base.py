from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from typing import Any, Mapping

from .busca import ClienteTavily
from .config import Config
from .jw import ClienteJW

NOME_PESQUISA = "pesquisar_web"
NOME_LEMBRAR = "lembrar"
NOME_AJUSTAR = "ajustar_preferencia"
NOME_ESQUECER = "esquecer"
NOME_JW = "jw"
NOME_AGENDAR = "agendar"
NOME_CONSULTAR_AGENDA = "consultar_agenda"
NOME_CANCELAR_COMPROMISSO = "cancelar_compromisso"
NOME_TEXTO_DIARIO = "texto_diario"

_MAX_AJUSTES = 20
_MAX_MEMORIAS = 100
_MAX_AGENDA = 50
_TAMANHO_MAXIMO_FATO = 300
_TAMANHO_MAXIMO_PREFERENCIA = 200
_TAMANHO_MAXIMO_TITULO_AGENDA = 120
_DURACAO_PADRAO_MINUTOS = 60
_MAX_LEMBRETE_MINUTOS = 10080
_JANELA_PADRAO_DIAS = 30


class FerramentaDesconhecida(Exception):
    def __init__(self, nome: str) -> None:
        super().__init__(f"ferramenta desconhecida: {nome}")
        self.nome = nome


class FerramentaInvalida(Exception):
    def __init__(self, detalhe: str) -> None:
        super().__init__(detalhe)
        self.detalhe = detalhe


@dataclass(frozen=True)
class ContextoFerramentas:
    busca: ClienteTavily | None = None
    jw: ClienteJW | None = None
    banco: Any | None = None
    pessoa_id: str | None = None
    mensagem_usuario: str = ""
    config: Config | None = None


def _ler_argumentos(argumentos: str | Mapping | None) -> dict:
    if isinstance(argumentos, Mapping):
        return dict(argumentos)
    try:
        dados = json.loads(argumentos or "{}")
    except json.JSONDecodeError as erro:
        raise FerramentaInvalida("argumentos não são JSON válido") from erro
    if not isinstance(dados, dict):
        raise FerramentaInvalida("argumentos precisam ser um objeto JSON")
    return dados


def _normalizar_texto(texto: Any) -> str:
    if not isinstance(texto, str):
        return ""
    decomposto = unicodedata.normalize("NFKD", " ".join(texto.split()))
    return "".join(
        caractere
        for caractere in decomposto
        if not unicodedata.combining(caractere)
    ).casefold()
