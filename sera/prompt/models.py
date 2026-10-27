from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any, Mapping


class FaixaEtaria(StrEnum):
    ADULTO = "adulto"
    ADOLESCENTE = "adolescente"
    CRIANCA = "crianca"


class Perfil(StrEnum):
    PADRAO = "padrao"
    CRIANCA_ADOLESCENTE = "crianca_adolescente"
    IDOSO_OU_POUCO_TECNICO = "idoso_ou_pouco_tecnico"


class NivelSarcasmo(StrEnum):
    NENHUM = "nenhum"
    LEVE = "leve"
    MEDIO = "medio"
    ALTO = "alto"


class Formalidade(StrEnum):
    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"


class NivelTecnico(StrEnum):
    BAIXO = "baixo"
    MEDIO = "medio"
    ALTO = "alto"


class ToqueYandere(StrEnum):
    DESLIGADO = "desligado"
    LEVE = "leve"
    MEDIO = "medio"


class TipoAjuste(StrEnum):
    APELIDO = "apelido"
    PIADA_INTERNA = "piada_interna"
    FORMATO = "formato"
    ASSUNTO = "assunto"
    NIVEL_SARCASMO = "nivel_sarcasmo"
    FORMALIDADE = "formalidade"
    NIVEL_TECNICO = "nivel_tecnico"
    TOQUE_YANDERE = "toque_yandere"


class OrigemAjuste(StrEnum):
    CONVERSA = "conversa"
    MANUAL = "manual"


class CategoriaFato(StrEnum):
    FAMILIA = "familia"
    TRABALHO = "trabalho"
    GOSTOS = "gostos"
    ROTINA = "rotina"
    SAUDE = "saude"
    OUTRO = "outro"


class Camada(StrEnum):
    LIMITES = "limites"
    BASE = "base"
    AJUSTES = "ajustes"
    MEMORIA = "memoria"
    CONTEXTO = "contexto"
    REFORCO = "reforco"


@dataclass(frozen=True)
class Pessoa:
    nome: str
    faixa_etaria: FaixaEtaria
    perfil: Perfil = Perfil.PADRAO


@dataclass(frozen=True)
class AjusteAprendido:
    tipo: TipoAjuste
    texto: str | None = None
    valor: str | None = None
    origem: OrigemAjuste = OrigemAjuste.CONVERSA
    criado_em: date | None = None


@dataclass(frozen=True)
class Fato:
    texto: str
    categoria: CategoriaFato = CategoriaFato.OUTRO
    criado_em: date | None = None


@dataclass(frozen=True)
class MemoriaDaPessoa:
    fatos: tuple[Fato, ...] = ()
    nao_mencionar: tuple[str, ...] = ()


@dataclass(frozen=True)
class Trecho:
    nota: str
    secao: str
    texto: str


@dataclass(frozen=True)
class Personality:
    versao: int
    limites_inviolaveis: Mapping[str, tuple[str, ...]]
    identidade: Mapping[str, Any]
    tom: Mapping[str, Any]
    humor: Mapping[str, Any]
    toque_yandere: Mapping[str, Any]
    como_explica: Mapping[str, Any]
    ajuda: Mapping[str, Any]
    adaptacao_por_usuario: Mapping[str, Any]
    memoria: Mapping[str, Any]
    camada_aprendida: Mapping[str, Any]
    situacoes: Mapping[str, Any]
    exemplos_de_voz: Mapping[str, Any]


@dataclass(frozen=True)
class KnobsEfetivos:
    nivel_sarcasmo: NivelSarcasmo
    formalidade: Formalidade
    nivel_tecnico: NivelTecnico
    toque_yandere: ToqueYandere
    tamanho_respostas: str
    tom_extra: str | None = None


@dataclass(frozen=True)
class Aviso:
    codigo: str
    detalhe: str

    def __str__(self) -> str:
        return f"[{self.codigo}] {self.detalhe}"


@dataclass(frozen=True)
class Bloco:
    camada: Camada
    titulo: str
    conteudo: str

    @property
    def texto(self) -> str:
        return f"{self.titulo}\n\n{self.conteudo}"


@dataclass(frozen=True)
class PromptMontado:
    blocos: tuple[Bloco, ...]
    knobs: KnobsEfetivos
    avisos: tuple[Aviso, ...]
    separador: str = "\n\n"

    def render(self) -> str:
        return self.separador.join(bloco.texto for bloco in self.blocos)

    @property
    def camadas(self) -> tuple[Camada, ...]:
        return tuple(bloco.camada for bloco in self.blocos)

    @property
    def chars(self) -> dict[str, int]:
        return {bloco.camada.value: len(bloco.texto) for bloco in self.blocos}
