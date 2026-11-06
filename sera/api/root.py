from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import Config

PEDIDO_TTL = 300.0
MAX_ERROS = 10
JANELA_ATENCAO = 600.0


@dataclass(frozen=True)
class ErroRecente:
    quando: float
    origem: str
    detalhe: str


class Diagnostico:
    """Estado em memória para o modo root (uma instância por processo)."""

    def __init__(self) -> None:
        self._inicio = time.time()
        self._erros: deque[ErroRecente] = deque(maxlen=MAX_ERROS)
        self._ultimo_sucesso: float | None = None
        self._ultimo_fallback: float | None = None
        self._modelo_usado: str | None = None

    def erro(self, origem: str, detalhe: str) -> None:
        self._erros.append(
            ErroRecente(
                quando=time.time(),
                origem=origem,
                detalhe=" ".join(detalhe.split())[:400],
            )
        )

    def sucesso(self, modelo: str | None = None) -> None:
        self._ultimo_sucesso = time.time()
        if modelo:
            self._modelo_usado = modelo

    def fallback(self) -> None:
        self._ultimo_fallback = time.time()

    def limpar(self) -> None:
        self._erros.clear()
        self._ultimo_sucesso = None
        self._ultimo_fallback = None
        self._modelo_usado = None
        self._inicio = time.time()

    @property
    def inicio(self) -> float:
        return self._inicio

    @property
    def ultimo_sucesso(self) -> float | None:
        return self._ultimo_sucesso

    @property
    def ultimo_fallback(self) -> float | None:
        return self._ultimo_fallback

    @property
    def modelo_usado(self) -> str | None:
        return self._modelo_usado

    def erros(self) -> list[ErroRecente]:
        return list(self._erros)


DIAGNOSTICO = Diagnostico()


@dataclass(frozen=True)
class ComandoRoot:
    resposta: str
    texto_usuario: str


class Root:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._senha = config.root_senha
        self._pedidos: dict[str, float] = {}

    @property
    def ativo(self) -> bool:
        return bool(self._senha)

    def _limpar(self) -> None:
        agora = time.monotonic()
        for conversa_id, limite in list(self._pedidos.items()):
            if limite <= agora:
                self._pedidos.pop(conversa_id, None)

    def processar(self, conversa_id: str, texto: str) -> ComandoRoot | None:
        """Trata /root e a senha sem deixar a senha chegar ao modelo ou ao banco."""
        if not self.ativo:
            return None
        self._limpar()

        if texto.strip().lower() == "/root":
            self._pedidos[conversa_id] = time.monotonic() + PEDIDO_TTL
            return ComandoRoot(
                resposta=(
                    "Modo root ativado. Digite a senha para ver o "
                    "diagnóstico da Sera."
                ),
                texto_usuario=texto,
            )

        if conversa_id not in self._pedidos:
            return None

        self._pedidos.pop(conversa_id, None)
        if texto.strip() != self._senha:
            return ComandoRoot(
                resposta="Senha incorreta. Use /root para tentar de novo.",
                texto_usuario="••••••",
            )

        return ComandoRoot(
            resposta=_diagnostico(self._config),
            texto_usuario="••••••",
        )


def _diagnostico(config: Config) -> str:
    agora = time.time()
    erros = DIAGNOSTICO.erros()
    recentes = [erro for erro in erros if agora - erro.quando <= JANELA_ATENCAO]
    estado = "atenção (erro recente)" if recentes else "operacional"

    linhas = [
        "## Sera — modo root",
        "",
        f"**Estado:** {estado}",
        f"**Modelo principal:** `{config.llm_model}` ({config.llm_provider})",
        f"**Modelo da última resposta:** `{DIAGNOSTICO.modelo_usado or '—'}`",
        "**Fallback:** "
        + (
            f"`{config.llm_fallback_model}`"
            if config.fallback_ativa
            else "desativado"
        ),
        f"**Uptime:** {_duracao(agora - DIAGNOSTICO.inicio)}",
        "**Última resposta concluída:** "
        + _desde(DIAGNOSTICO.ultimo_sucesso, agora),
    ]
    if DIAGNOSTICO.ultimo_fallback is not None:
        linhas.append(
            "**Último uso do fallback:** "
            + _desde(DIAGNOSTICO.ultimo_fallback, agora)
        )

    linhas.extend(
        [
            "",
            "### Configuração",
            "- Busca web: "
            + (
                f"ativa (Tavily, até {config.busca_max_resultados} resultados, "
                f"{config.busca_max_rodadas} rodada de ferramenta)"
                if config.busca_ativa
                else "desativada"
            ),
            f"- JW: {'ativo' if config.jw_ativa else 'desativado'}",
            f"- Agenda/lembretes: "
            f"{'ativos' if config.agenda_ativa else 'desativados'}",
            f"- Texto diário: "
            f"{'ativo' if config.texto_diario_ativa else 'desativado'}",
            f"- Aprendizado/memória: "
            f"{'ligado' if config.aprendizado_habilitado else 'desligado'}",
            f"- Dados: {'Supabase' if config.supabase_url else 'SQLite local'}",
            f"- Autenticação: {'JWT' if config.auth_required else 'livre (dev)'}",
            f"- Temperatura / max tokens: {config.temperatura} / {config.max_tokens}",
            "",
            "### Funcionamento do chat",
            "- Resposta por streaming (SSE): `start` → `token` → `done`.",
            "- Histórico enviado ao modelo: até "
            f"{config.max_history_mensagens} mensagens / "
            f"{config.max_history_chars} caracteres.",
            "- Contexto de memória: até "
            f"{config.max_trechos_contexto} trechos / "
            f"{config.max_chars_contexto} caracteres.",
            "- Ferramentas: pesquisar_web, jw, agendar, consultar_agenda, "
            "cancelar_compromisso, texto_diario, lembrar, "
            "ajustar_preferencia, esquecer.",
            "- Agenda, texto diário e JW só entram quando a mensagem pede.",
        ]
    )

    linhas.extend(["", "### Erros recentes"])
    if not erros:
        linhas.append("- Nenhum erro registrado desde o start.")
    else:
        for erro in list(reversed(erros))[:5]:
            linhas.append(
                f"- {_quando(erro.quando, config.fuso_horario)} — "
                f"**{erro.origem}**: {erro.detalhe}"
            )
    return "\n".join(linhas)


def _quando(instante: float, fuso: str) -> str:
    return datetime.fromtimestamp(instante, ZoneInfo(fuso)).strftime(
        "%d/%m %H:%M:%S"
    )


def _desde(instante: float | None, agora: float) -> str:
    if instante is None:
        return "nenhuma desde o start"
    segundos = max(0, int(agora - instante))
    if segundos < 10:
        return "agora"
    if segundos < 60:
        return f"há {segundos}s"
    minutos = segundos // 60
    if minutos < 60:
        return f"há {minutos}min"
    horas = minutos // 60
    if horas < 24:
        return f"há {horas}h"
    return f"há {horas // 24}d"


def _duracao(segundos: float) -> str:
    total = max(0, int(segundos))
    dias, resto = divmod(total, 86400)
    horas, resto = divmod(resto, 3600)
    minutos = resto // 60
    partes: list[str] = []
    if dias:
        partes.append(f"{dias}d")
    if horas:
        partes.append(f"{horas}h")
    partes.append(f"{minutos}min")
    return " ".join(partes)
