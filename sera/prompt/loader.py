from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from .errors import PersonalityInvalida
from .models import (
    Formalidade,
    NivelSarcasmo,
    NivelTecnico,
    Personality,
    ToqueYandere,
)

VERSAO_SUPORTADA = 1

_SECOES = (
    "identidade",
    "tom",
    "humor",
    "toque_yandere",
    "como_explica",
    "ajuda",
    "adaptacao_por_usuario",
    "memoria",
    "camada_aprendida",
    "situacoes",
    "exemplos_de_voz",
)

_KNOBS = {
    "nivel_sarcasmo": NivelSarcasmo,
    "formalidade": Formalidade,
    "nivel_tecnico": NivelTecnico,
    "toque_yandere": ToqueYandere,
}

_PRESETS = (
    "padrao",
    "perfil_crianca_adolescente",
    "perfil_idoso_ou_pouco_tecnico",
)


def carregar_personality(caminho: str | Path) -> Personality:
    caminho = Path(caminho)
    try:
        bruto = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    except FileNotFoundError as erro:
        raise PersonalityInvalida(f"arquivo não encontrado: {caminho}") from erro
    except yaml.YAMLError as erro:
        raise PersonalityInvalida(f"YAML inválido em {caminho}: {erro}") from erro

    if not isinstance(bruto, Mapping):
        raise PersonalityInvalida("o arquivo precisa ser um mapa YAML")

    versao = bruto.get("versao")
    if versao != VERSAO_SUPORTADA:
        raise PersonalityInvalida(
            f"versão {versao!r} não suportada; esperada {VERSAO_SUPORTADA}"
        )

    limites = _validar_limites(bruto.get("limites_inviolaveis"))

    secoes: dict[str, Mapping[str, Any]] = {}
    for nome in _SECOES:
        valor = bruto.get(nome)
        if not isinstance(valor, Mapping) or not valor:
            raise PersonalityInvalida(f"seção {nome!r} ausente ou vazia")
        secoes[nome] = valor

    _validar_identidade(secoes["identidade"])
    _validar_adaptacao(secoes["adaptacao_por_usuario"])

    return Personality(
        versao=versao,
        limites_inviolaveis=limites,
        identidade=secoes["identidade"],
        tom=secoes["tom"],
        humor=secoes["humor"],
        toque_yandere=secoes["toque_yandere"],
        como_explica=secoes["como_explica"],
        ajuda=secoes["ajuda"],
        adaptacao_por_usuario=secoes["adaptacao_por_usuario"],
        memoria=secoes["memoria"],
        camada_aprendida=secoes["camada_aprendida"],
        situacoes=secoes["situacoes"],
        exemplos_de_voz=secoes["exemplos_de_voz"],
    )


def _validar_limites(valor: Any) -> dict[str, tuple[str, ...]]:
    if not isinstance(valor, Mapping) or not valor:
        raise PersonalityInvalida("limites_inviolaveis ausente ou vazio")

    limites: dict[str, tuple[str, ...]] = {}
    for categoria, itens in valor.items():
        if not isinstance(categoria, str) or not categoria.strip():
            raise PersonalityInvalida("categoria de limite inválida")
        if not isinstance(itens, list) or not itens:
            raise PersonalityInvalida(
                f"limite {categoria!r} precisa ser uma lista não vazia"
            )
        textos = []
        for item in itens:
            if not isinstance(item, str) or not item.strip():
                raise PersonalityInvalida(
                    f"limite {categoria!r} contém um item vazio ou não textual"
                )
            textos.append(item.strip())
        limites[categoria.strip()] = tuple(textos)
    return limites


def _validar_identidade(identidade: Mapping[str, Any]) -> None:
    nome = identidade.get("nome")
    if not isinstance(nome, str) or not nome.strip():
        raise PersonalityInvalida("identidade.nome é obrigatório")


def _validar_adaptacao(adaptacao: Mapping[str, Any]) -> None:
    padrao = adaptacao.get("padrao")
    if not isinstance(padrao, Mapping):
        raise PersonalityInvalida("adaptacao_por_usuario.padrao ausente")

    for chave, enum in _KNOBS.items():
        if chave not in padrao:
            raise PersonalityInvalida(f"adaptacao_por_usuario.padrao.{chave} ausente")
        _validar_knob(chave, padrao[chave], enum, "adaptacao_por_usuario.padrao")

    if "tamanho_respostas" not in padrao:
        raise PersonalityInvalida(
            "adaptacao_por_usuario.padrao.tamanho_respostas ausente"
        )

    for preset in _PRESETS:
        valores = adaptacao.get(preset)
        if valores is None:
            continue
        if not isinstance(valores, Mapping):
            raise PersonalityInvalida(
                f"adaptacao_por_usuario.{preset} precisa ser um mapa"
            )
        for chave, enum in _KNOBS.items():
            if chave in valores:
                _validar_knob(
                    chave, valores[chave], enum, f"adaptacao_por_usuario.{preset}"
                )


def _validar_knob(chave: str, valor: Any, enum: type, onde: str) -> None:
    try:
        enum(valor)
    except (TypeError, ValueError) as erro:
        permitidos = ", ".join(membro.value for membro in enum)
        raise PersonalityInvalida(
            f"{onde}.{chave} inválido: {valor!r}; permitidos: {permitidos}"
        ) from erro
