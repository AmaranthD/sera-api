from __future__ import annotations

import logging
from typing import Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..prompt import carregar_personality
from .auth import Autenticador, AutenticadorSupabase
from .config import Config
from .db import Banco
from .db_supabase import BancoSupabase
from .llm import ClienteGemini, ClienteLLM, ClienteOpenAICompat
from .rotas import router

logger = logging.getLogger(__name__)

FabricaBanco = Callable[[str | None], BancoSupabase]


def criar_app(
    config: Config | None = None,
    *,
    llm: ClienteLLM | None = None,
    banco: Banco | None = None,
    autenticador: Autenticador | None = None,
) -> FastAPI:
    config = config or Config.de_env()

    fabrica: FabricaBanco | None = None
    banco_local: Banco | None = None
    if banco is not None:
        banco_local = banco
        banco_local.iniciar()
    elif config.supabase_url and config.supabase_anon_key:
        fabrica = lambda token: BancoSupabase(config, token or "")
    else:
        banco_local = Banco(config.db_path)
        banco_local.iniciar()

    personality = carregar_personality(config.personality_path)

    app = FastAPI(title="Sera", version="0.3.0")
    app.state.config = config
    app.state.banco = banco_local
    app.state.banco_fabrica = fabrica
    app.state.llm = llm or _criar_llm(config)
    app.state.personality = personality
    app.state.autenticador = autenticador
    if config.auth_required and app.state.autenticador is None:
        app.state.autenticador = AutenticadorSupabase(config)

    logger.info(
        "Sera iniciada: backend=%s provedor=%s modelo=%s auth=%s",
        "supabase" if fabrica is not None else f"sqlite:{config.db_path}",
        config.llm_provider,
        config.llm_model,
        "jwt" if config.auth_required else "dev",
    )
    if config.auth_required and not config.emails_permitidos:
        logger.warning(
            "SERA_EMAILS não definido: qualquer conta autenticada pode usar "
            "a API; feche o cadastro no Supabase ou defina a lista"
        )
    if config.llm_provider == "openai" and config.base_incompleta:
        logger.warning(
            "LLM_BASE_URL=%r não termina em /v1 nem em /chat/completions; "
            "usando %s",
            config.llm_base_url,
            config.url_chat,
        )

    if config.cors_origins or config.cors_origin_regex:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(config.cors_origins),
            allow_origin_regex=config.cors_origin_regex,
            allow_credentials=False,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
            max_age=600,
        )

    app.include_router(router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


def _criar_llm(config: Config) -> ClienteLLM:
    if config.llm_provider == "gemini":
        return ClienteGemini(config)
    return ClienteOpenAICompat(config)
