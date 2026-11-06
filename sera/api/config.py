from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_RAIZ = Path(__file__).resolve().parents[2]
_ARQUIVOS_ENV = (Path(".env"), _RAIZ / ".env", _RAIZ / "sera" / "api" / ".env")


def _ler_dotenv(caminho: Path) -> dict[str, str]:
    try:
        linhas = caminho.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return {}
    valores: dict[str, str] = {}
    for linha in linhas:
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        if linha.startswith("export "):
            linha = linha.removeprefix("export ").strip()
        chave, separador, valor = linha.partition("=")
        if not separador:
            continue
        chave = chave.strip()
        if not chave:
            continue
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        valores[chave] = valor
    return valores


def _carregar_env() -> None:
    for caminho in _ARQUIVOS_ENV:
        for chave, valor in _ler_dotenv(caminho).items():
            os.environ.setdefault(chave, valor)


@dataclass(frozen=True)
class Config:
    db_path: Path = Path("data/sera.db")
    personality_path: Path = Path("personality.yaml")
    llm_provider: str = "gemini"
    gemini_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str | None = None
    llm_model: str = "gemini-3.8-flash"
    llm_fallback_base_url: str | None = None
    llm_fallback_api_key: str | None = None
    llm_fallback_model: str | None = None
    temperatura: float = 0.8
    max_tokens: int = 1024
    connect_timeout: float = 10.0
    read_timeout: float = 120.0
    max_history_mensagens: int = 20
    max_history_chars: int = 12000
    notas_path: Path = _RAIZ.parent / "notes" / "Notes"
    max_trechos_contexto: int = 3
    max_chars_contexto: int = 6000
    busca_habilitada: bool = False
    busca_provedor: str = "tavily"
    tavily_api_key: str | None = None
    busca_max_resultados: int = 5
    busca_timeout: float = 15.0
    busca_cache_ttl: float = 600.0
    busca_pais: str = "BR"
    busca_max_rodadas: int = 1
    jw_api_url: str | None = None
    jw_api_key: str | None = None
    jw_timeout: float = 90.0
    jw_max_chars: int = 8000
    jw_max_rodadas: int = 2
    fuso_horario: str = "America/Sao_Paulo"
    aprendizado_habilitado: bool = True
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_key: str | None = None
    supabase_jwt_aud: str = "authenticated"
    vapid_public_key: str | None = None
    vapid_private_key: str | None = None
    vapid_subject: str = "mailto:contato@sera.local"
    notificacoes_segredo: str | None = None
    notificacoes_intervalo: float = 60.0
    notificacoes_preview: bool = False
    tts_habilitado: bool = False
    tts_voz: str = "pt-BR-FranciscaNeural"
    tts_rate: str = "+0%"
    tts_pitch: str = "+0Hz"
    tts_volume: str = "+0%"
    cors_origins: tuple[str, ...] = ()
    cors_origin_regex: str | None = None
    emails_permitidos: tuple[str, ...] = ()
    auth_required: bool = False

    def __post_init__(self) -> None:
        if self.max_tokens <= 0:
            raise ValueError("max_tokens precisa ser positivo")
        if self.max_history_mensagens <= 0:
            raise ValueError("max_history_mensagens precisa ser positivo")
        if self.max_history_chars <= 0:
            raise ValueError("max_history_chars precisa ser positivo")
        if self.max_trechos_contexto < 0:
            raise ValueError("max_trechos_contexto não pode ser negativo")
        if self.max_chars_contexto <= 0:
            raise ValueError("max_chars_contexto precisa ser positivo")
        if self.busca_provedor != "tavily":
            raise ValueError(
                f"busca_provedor inválido: {self.busca_provedor!r}; "
                "por enquanto só 'tavily' é suportado"
            )
        if self.busca_max_resultados <= 0:
            raise ValueError("busca_max_resultados precisa ser positivo")
        if self.busca_timeout <= 0:
            raise ValueError("busca_timeout precisa ser positivo")
        if self.busca_cache_ttl < 0:
            raise ValueError("busca_cache_ttl não pode ser negativo")
        if self.busca_max_rodadas < 1:
            raise ValueError("busca_max_rodadas precisa ser pelo menos 1")
        if self.jw_timeout <= 0:
            raise ValueError("jw_timeout precisa ser positivo")
        if self.jw_max_chars <= 0:
            raise ValueError("jw_max_chars precisa ser positivo")
        if self.jw_max_rodadas < 1:
            raise ValueError("jw_max_rodadas precisa ser pelo menos 1")
        if self.jw_api_url:
            partes_jw = urlparse(self.jw_api_url)
            if partes_jw.scheme not in ("http", "https") or not partes_jw.netloc:
                raise ValueError(
                    f"jw_api_url inválida: {self.jw_api_url!r}; "
                    "use uma URL http(s) absoluta"
                )
        try:
            ZoneInfo(self.fuso_horario)
        except (ValueError, ZoneInfoNotFoundError) as erro:
            raise ValueError(
                f"fuso_horario inválido: {self.fuso_horario!r}"
            ) from erro
        if self.llm_provider not in ("gemini", "openai"):
            raise ValueError(
                f"llm_provider inválido: {self.llm_provider!r}; "
                "use 'gemini' ou 'openai'"
            )
        if not self.llm_model.strip():
            raise ValueError("llm_model é obrigatório")
        if not self.llm_base_url.strip():
            raise ValueError("llm_base_url é obrigatório")
        partes = urlparse(self._base_limpa())
        if partes.scheme not in ("http", "https") or not partes.netloc:
            raise ValueError(
                f"llm_base_url inválida: {self.llm_base_url!r}; "
                "use uma URL http(s) absoluta"
            )
        if any(
            (
                self.llm_fallback_base_url,
                self.llm_fallback_api_key,
                self.llm_fallback_model,
            )
        ):
            if not (self.llm_fallback_base_url and self.llm_fallback_model):
                raise ValueError(
                    "defina LLM_FALLBACK_BASE_URL e LLM_FALLBACK_MODEL "
                    "juntas para ativar o fallback"
                )
            partes_fallback = urlparse(self.llm_fallback_base_url.strip())
            if (
                partes_fallback.scheme not in ("http", "https")
                or not partes_fallback.netloc
            ):
                raise ValueError(
                    f"llm_fallback_base_url inválida: "
                    f"{self.llm_fallback_base_url!r}; use uma URL http(s) "
                    "absoluta"
                )
        if self.auth_required and not self.supabase_url:
            raise ValueError(
                "SUPABASE_URL é obrigatória quando a autenticação está ligada; "
                "para rodar local sem Supabase defina SERA_DEV=1"
            )
        if self.supabase_url and not self.supabase_anon_key:
            raise ValueError(
                "SUPABASE_ANON_KEY (ou SUPABASE_PUBLISHABLE_KEY) é obrigatória "
                "quando SUPABASE_URL está definida"
            )
        if bool(self.vapid_public_key) != bool(self.vapid_private_key):
            raise ValueError(
                "VAPID_PUBLIC_KEY e VAPID_PRIVATE_KEY precisam ser definidas "
                "juntas"
            )
        if self.vapid_subject and not (
            self.vapid_subject.startswith("mailto:")
            or self.vapid_subject.startswith("https://")
        ):
            raise ValueError(
                "VAPID_SUBJECT precisa começar com 'mailto:' ou 'https://'"
            )
        if self.notificacoes_intervalo <= 0:
            raise ValueError("notificacoes_intervalo precisa ser positivo")

    def _base_limpa(self) -> str:
        return self.llm_base_url.strip().rstrip("/")

    def _base_fallback_limpa(self) -> str:
        return (self.llm_fallback_base_url or "").strip().rstrip("/")

    @property
    def fallback_ativa(self) -> bool:
        return bool(self.llm_fallback_base_url and self.llm_fallback_model)

    @property
    def url_chat_fallback(self) -> str:
        base = self._base_fallback_limpa()
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    @property
    def busca_ativa(self) -> bool:
        return self.busca_habilitada and bool(self.tavily_api_key)

    @property
    def jw_ativa(self) -> bool:
        return bool(self.jw_api_url and self.jw_api_key)

    @property
    def notificacoes_ativas(self) -> bool:
        return bool(self.vapid_public_key and self.vapid_private_key)

    @property
    def tts_ativa(self) -> bool:
        return self.tts_habilitado

    @property
    def agenda_ativa(self) -> bool:
        """Há como disparar lembretes (push configurado e banco admin)."""
        if not self.notificacoes_ativas:
            return False
        if self.supabase_url and not self.supabase_service_key:
            return False
        return True

    @property
    def texto_diario_ativa(self) -> bool:
        """O cron do texto diário precisa do banco administrativo.

        Diferente dos lembretes, não exige VAPID: a entrega na conversa
        funciona mesmo sem notificações; o push é só um extra.
        """
        if self.supabase_url and not self.supabase_service_key:
            return False
        return True

    @property
    def url_chat(self) -> str:
        base = self._base_limpa()
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    @property
    def base_incompleta(self) -> bool:
        base = self._base_limpa()
        return not base.endswith("/v1") and not base.endswith("/chat/completions")

    @classmethod
    def de_env(cls, env: Mapping[str, str] | None = None) -> "Config":
        if env is None:
            _carregar_env()
        valores = os.environ if env is None else env

        def texto(chave: str, padrao: str) -> str:
            return (valores.get(chave) or padrao).strip()

        def opcional(chave: str) -> str | None:
            return texto(chave, "") or None

        def numero(chave: str, padrao: float) -> float:
            bruto = valores.get(chave)
            return padrao if bruto is None or not bruto.strip() else float(bruto)

        def inteiro(chave: str, padrao: int) -> int:
            bruto = valores.get(chave)
            return padrao if bruto is None or not bruto.strip() else int(bruto)

        return cls(
            db_path=Path(texto("SERA_DB", "data/sera.db")),
            personality_path=Path(texto("SERA_PERSONALITY", "personality.yaml")),
            llm_provider=texto("LLM_PROVIDER", "gemini").lower(),
            gemini_api_key=(
                opcional("GEMINI_API_KEY")
                or opcional("GOOGLE_API_KEY")
                or opcional("LLM_API_KEY")
            ),
            llm_base_url=texto("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            llm_api_key=opcional("LLM_API_KEY"),
            llm_model=texto("LLM_MODEL", "gemini-3.8-flash"),
            llm_fallback_base_url=opcional("LLM_FALLBACK_BASE_URL"),
            llm_fallback_api_key=opcional("LLM_FALLBACK_API_KEY"),
            llm_fallback_model=opcional("LLM_FALLBACK_MODEL"),
            temperatura=numero("LLM_TEMPERATURE", 0.8),
            max_tokens=inteiro("LLM_MAX_TOKENS", 1024),
            connect_timeout=numero("LLM_CONNECT_TIMEOUT", 10.0),
            read_timeout=numero("LLM_READ_TIMEOUT", 120.0),
            max_history_mensagens=inteiro("SERA_MAX_HISTORY_MENSAGENS", 20),
            max_history_chars=inteiro("SERA_MAX_HISTORY_CHARS", 12000),
            notas_path=Path(texto("SERA_NOTAS", str(_RAIZ.parent / "notes" / "Notes"))),
            max_trechos_contexto=inteiro("SERA_MAX_TRECHOS", 3),
            max_chars_contexto=inteiro("SERA_MAX_CHARS_CONTEXTO", 6000),
            busca_habilitada=texto("BUSCA_HABILITADA", "false").lower()
            in ("1", "true", "yes", "on"),
            busca_provedor=texto("BUSCA_PROVEDOR", "tavily").lower(),
            tavily_api_key=(
                opcional("TAVILY_API_KEY") or opcional("Tavily_API_KEY")
            ),
            busca_max_resultados=inteiro("BUSCA_MAX_RESULTADOS", 5),
            busca_timeout=numero("BUSCA_TIMEOUT", 15.0),
            busca_cache_ttl=numero("BUSCA_CACHE_TTL", 600.0),
            busca_pais=texto("BUSCA_PAIS", "BR"),
            busca_max_rodadas=inteiro("BUSCA_MAX_RODADAS", 1),
            jw_api_url=opcional("JW_API_URL"),
            jw_api_key=opcional("JW_API_KEY"),
            jw_timeout=numero("JW_TIMEOUT", 90.0),
            jw_max_chars=inteiro("JW_MAX_CHARS", 8000),
            jw_max_rodadas=inteiro("JW_MAX_RODADAS", 2),
            fuso_horario=texto("SERA_FUSO", "America/Sao_Paulo"),
            aprendizado_habilitado=texto("SERA_APRENDIZADO", "true").lower()
            in ("1", "true", "yes", "on"),
            supabase_url=opcional("SUPABASE_URL"),
            supabase_anon_key=(
                opcional("SUPABASE_ANON_KEY")
                or opcional("SUPABASE_PUBLISHABLE_KEY")
            ),
            supabase_service_key=opcional("SUPABASE_SERVICE_KEY"),
            supabase_jwt_aud=texto("SUPABASE_JWT_AUD", "authenticated"),
            vapid_public_key=opcional("VAPID_PUBLIC_KEY"),
            vapid_private_key=opcional("VAPID_PRIVATE_KEY"),
            vapid_subject=texto("VAPID_SUBJECT", "mailto:contato@sera.local"),
            notificacoes_segredo=opcional("NOTIFICACOES_SEGREDO"),
            notificacoes_intervalo=numero("NOTIFICACOES_INTERVALO", 60.0),
            notificacoes_preview=texto("NOTIFICACOES_PREVIEW", "false")
            .lower()
            in ("1", "true", "yes", "on"),
            tts_habilitado=texto("TTS_HABILITADO", "false").lower()
            in ("1", "true", "yes", "on"),
            tts_voz=texto("TTS_VOZ", "pt-BR-FranciscaNeural"),
            tts_rate=texto("TTS_RATE", "+0%"),
            tts_pitch=texto("TTS_PITCH", "+0Hz"),
            tts_volume=texto("TTS_VOLUME", "+0%"),
            cors_origins=tuple(
                origem.strip()
                for origem in texto("CORS_ORIGINS", "").split(",")
                if origem.strip()
            ),
            cors_origin_regex=opcional("CORS_ORIGIN_REGEX"),
            emails_permitidos=tuple(
                email.strip().lower()
                for email in texto("SERA_EMAILS", "").split(",")
                if email.strip()
            ),
            auth_required=texto("SERA_DEV", "").lower()
            not in ("1", "true", "yes", "on"),
        )
