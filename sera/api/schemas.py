from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

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


class MemoriaAtualizacao(BaseModel):
    texto: FatoTexto | None = None
    categoria: CategoriaFato | None = None


class TemaEntrada(BaseModel):
    tema: Tema


class AjusteEntrada(BaseModel):
    tipo: TipoAjuste
    texto: str | None = None
    valor: str | None = None
    origem: OrigemAjuste = OrigemAjuste.MANUAL


class AjusteAtualizacao(BaseModel):
    texto: str | None = None
    valor: str | None = None


class ChatEntrada(BaseModel):
    pessoa_id: Identificador | None = None
    mensagem: Mensagem
    conversa_id: str | None = None
    stream: bool = True
    # "jw" liga o modo de fonte única: só Bíblia/publicações JW respondem.
    fonte: Literal["jw"] | None = None


TituloCompromisso = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]
DescricaoCompromisso = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=2000)
]
FusoHorario = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]


def _validar_intervalo(inicio: datetime, fim: datetime) -> None:
    if inicio.tzinfo is None or fim.tzinfo is None:
        raise ValueError("início e fim precisam ter fuso horário")
    if fim <= inicio:
        raise ValueError("o fim precisa ser depois do início")


class CompromissoEntrada(BaseModel):
    titulo: TituloCompromisso
    descricao: DescricaoCompromisso = ""
    inicio: datetime
    fim: datetime
    fuso: FusoHorario | None = None
    lembrete_minutos: int = Field(default=10, ge=0, le=10080)

    @model_validator(mode="after")
    def validar(self) -> "CompromissoEntrada":
        _validar_intervalo(self.inicio, self.fim)
        return self


class CompromissoAtualizacao(BaseModel):
    titulo: TituloCompromisso | None = None
    descricao: DescricaoCompromisso | None = None
    inicio: datetime | None = None
    fim: datetime | None = None
    fuso: FusoHorario | None = None
    lembrete_minutos: int | None = Field(default=None, ge=0, le=10080)

    @field_validator("inicio", "fim")
    @classmethod
    def exigir_fuso(cls, valor: datetime | None) -> datetime | None:
        if valor is not None and valor.tzinfo is None:
            raise ValueError("data precisa ter fuso horário")
        return valor


class ChavesPush(BaseModel):
    p256dh: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    auth: Annotated[str, StringConstraints(min_length=1, max_length=100)]


class InscricaoPushEntrada(BaseModel):
    endpoint: Annotated[str, StringConstraints(min_length=8, max_length=1000)]
    keys: ChavesPush
    user_agent: Annotated[str, StringConstraints(max_length=300)] | None = None

    @field_validator("endpoint")
    @classmethod
    def endpoint_http(cls, valor: str) -> str:
        if not valor.startswith(("https://", "http://localhost")):
            raise ValueError("endpoint precisa ser uma URL https")
        return valor
