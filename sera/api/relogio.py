from __future__ import annotations

import re
from datetime import date, datetime, timedelta
_DIAS = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)

_MESES = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


def formatar_data(dia: date) -> str:
    return dia.strftime("%d/%m/%Y")


def nome_do_mes(dia: date) -> str:
    return f"{_MESES[dia.month - 1]} de {dia.year}"


def _intervalo(inicio: date, fim: date) -> str:
    return f"{formatar_data(inicio)} a {formatar_data(fim)}"


def bloco_agora(momento: datetime, fuso: str) -> str:
    """Bloco dinâmico de data/hora para entrar no system prompt."""
    dia = momento.date()
    inicio_semana = dia - timedelta(days=dia.weekday())
    fim_semana = inicio_semana + timedelta(days=6)
    inicio_semana_passada = inicio_semana - timedelta(days=7)
    fim_semana_passada = inicio_semana - timedelta(days=1)
    ultimos_sete = dia - timedelta(days=6)
    inicio_mes = dia.replace(day=1)
    fim_mes = (inicio_mes + timedelta(days=32)).replace(day=1) - timedelta(
        days=1
    )
    fim_mes_passado = inicio_mes - timedelta(days=1)
    inicio_mes_passado = fim_mes_passado.replace(day=1)

    linhas = [
        "# AGORA",
        (
            f"Data e hora: {_DIAS[dia.weekday()]}, "
            f"{formatar_data(dia)}, {momento.strftime('%H:%M')} ({fuso})."
        ),
        "",
        "Use estas datas absolutas quando a pessoa falar de tempo relativo, "
        "tanto na resposta quanto nas buscas na internet:",
        f'- "hoje" = {formatar_data(dia)}',
        f'- "ontem" = {formatar_data(dia - timedelta(days=1))}',
        f'- "amanhã" = {formatar_data(dia + timedelta(days=1))}',
        f'- "esta semana" = {_intervalo(inicio_semana, fim_semana)}',
        f'- "última semana" / "últimos 7 dias" = {_intervalo(ultimos_sete, dia)}',
        (
            '- "semana passada" = '
            f"{_intervalo(inicio_semana_passada, fim_semana_passada)}"
        ),
        f'- "este mês" = {nome_do_mes(inicio_mes)}'
        + ("" if fim_mes == inicio_mes else f" ({_intervalo(inicio_mes, fim_mes)})"),
        (
            '- "mês passado" = '
            f"{nome_do_mes(inicio_mes_passado)} "
            f"({_intervalo(inicio_mes_passado, fim_mes_passado)})"
        ),
        "",
        "Nunca diga que não sabe a data de hoje: consulte este bloco.",
    ]
    return "\n".join(linhas)


_SUBSTITUICOES = (
    (re.compile(r"\bhoje\s+em\s+dia\b", re.IGNORECASE), "atualmente"),
    (re.compile(r"\banteontem\b", re.IGNORECASE), "anteontem"),
    (re.compile(r"\bontem\b", re.IGNORECASE), "ontem"),
    (re.compile(r"\bamanh[ãa]\b", re.IGNORECASE), "amanha"),
    (re.compile(r"\bhoje\b", re.IGNORECASE), "hoje"),
    (
        re.compile(
            r"\b(?:esta|essa|nesta|desta)\s+semana\b", re.IGNORECASE
        ),
        "semana_atual",
    ),
    (
        re.compile(r"\b(?:semana\s+passada)\b", re.IGNORECASE),
        "semana_passada",
    ),
    (
        re.compile(r"\b(?:[úu]ltima|[úu]ltimos)\s+(?:semana|7\s+dias)\b", re.IGNORECASE),
        "ultimos_sete",
    ),
    (
        re.compile(
            r"\b(?:este|esse|neste|deste)\s+m[êe]s\b", re.IGNORECASE
        ),
        "mes_atual",
    ),
    (
        re.compile(
            r"\b(?:m[êe]s\s+passado|[úu]ltimo\s+m[êe]s)\b", re.IGNORECASE
        ),
        "mes_passado",
    ),
)


def normalizar_consulta(consulta: str, momento: datetime) -> str:
    """Troca referências relativas por datas absolutas antes de buscar."""
    dia = momento.date()
    valores = {
        "anteontem": formatar_data(dia - timedelta(days=2)),
        "ontem": formatar_data(dia - timedelta(days=1)),
        "amanha": formatar_data(dia + timedelta(days=1)),
        "hoje": formatar_data(dia),
        "semana_atual": _intervalo(
            dia - timedelta(days=dia.weekday()),
            dia - timedelta(days=dia.weekday()) + timedelta(days=6),
        ),
        "semana_passada": _intervalo(
            dia - timedelta(days=dia.weekday() + 7),
            dia - timedelta(days=dia.weekday() + 1),
        ),
        "ultimos_sete": _intervalo(dia - timedelta(days=6), dia),
        "mes_atual": nome_do_mes(dia),
        "mes_passado": nome_do_mes(dia.replace(day=1) - timedelta(days=1)),
    }

    texto = consulta
    for padrao, valor in _SUBSTITUICOES:
        if valor in valores:
            texto = padrao.sub(valores[valor], texto)
        elif valor is not None:
            texto = padrao.sub(valor, texto)
    return " ".join(texto.split())
