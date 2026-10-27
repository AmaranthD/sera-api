from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, StringConstraints

from ..prompt import CategoriaFato, FaixaEtaria, OrigemAjuste, Perfil, TipoAjuste

Identificador = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_-]{1,64}$"),
]
Nome = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
]
Mensagem = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)
]
FatoTexto = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]
Tema = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]


class PessoaEntrada(BaseModel):
    id: Identificador | None = None
    nome: Nome
    faixa_etaria: FaixaEtaria
    perfil: Perfil = Perfil.PADRAO
    acesso_vault: bool | None = None


class MemoriaEntrada(BaseModel):
    texto: FatoTexto
    categoria: CategoriaFato = CategoriaFato.OUTRO


class TemaEntrada(BaseModel):
    tema: Tema


class AjusteEntrada(BaseModel):
    tipo: TipoAjuste
    texto: str | None = None
    valor: str | None = None
    origem: OrigemAjuste = OrigemAjuste.MANUAL


class ChatEntrada(BaseModel):
    pessoa_id: Identificador | None = None
    mensagem: Mensagem
    conversa_id: str | None = None
    stream: bool = True
