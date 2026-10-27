from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

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
    temperatura: float = 0.8
    max_tokens: int = 1024
    connect_timeout: float = 10.0
    read_timeout: float = 120.0
    max_history_mensagens: int = 20
    max_history_chars: int = 12000
    notas_path: Path = _RAIZ.parent / "notes" / "Notes"
    max_trechos_contexto: int = 3
    max_chars_contexto: int = 6000
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_jwt_aud: str = "authenticated"
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

    def _base_limpa(self) -> str:
        return self.llm_base_url.strip().rstrip("/")

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
            temperatura=numero("LLM_TEMPERATURE", 0.8),
            max_tokens=inteiro("LLM_MAX_TOKENS", 1024),
            connect_timeout=numero("LLM_CONNECT_TIMEOUT", 10.0),
            read_timeout=numero("LLM_READ_TIMEOUT", 120.0),
            max_history_mensagens=inteiro("SERA_MAX_HISTORY_MENSAGENS", 20),
            max_history_chars=inteiro("SERA_MAX_HISTORY_CHARS", 12000),
            notas_path=Path(texto("SERA_NOTAS", str(_RAIZ.parent / "notes" / "Notes"))),
            max_trechos_contexto=inteiro("SERA_MAX_TRECHOS", 3),
            max_chars_contexto=inteiro("SERA_MAX_CHARS_CONTEXTO", 6000),
            supabase_url=opcional("SUPABASE_URL"),
            supabase_anon_key=(
                opcional("SUPABASE_ANON_KEY")
                or opcional("SUPABASE_PUBLISHABLE_KEY")
            ),
            supabase_jwt_aud=texto("SUPABASE_JWT_AUD", "authenticated"),
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
