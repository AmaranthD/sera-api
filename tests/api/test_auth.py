from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException

from sera.api import Config, criar_app
from sera.api.auth import Usuario
from sera.api.db import Banco
from tests.api.ajuda import FakeLLM, eventos

pytestmark = pytest.mark.anyio

RAIZ = Path(__file__).resolve().parents[2]


class FakeAutenticador:
    def __init__(
        self, tokens: dict[str, str], *, email: str | None = None
    ) -> None:
        self.tokens = tokens
        self.email = email

    async def validar(self, token: str) -> Usuario:
        pessoa_id = self.tokens.get(token)
        if pessoa_id is None:
            raise HTTPException(
                status_code=401,
                detail="token inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return Usuario(id=pessoa_id, token=token, email=self.email)


@pytest.fixture
def config(tmp_path) -> Config:
    return Config(
        db_path=tmp_path / "sera.db",
        personality_path=RAIZ / "personality.yaml",
        llm_base_url="http://fake.local/v1",
        llm_model="fake-model",
        supabase_url="https://fake.supabase.co",
        supabase_anon_key="anon",
        auth_required=True,
    )


@pytest.fixture
async def cliente(config):
    banco = Banco(config.db_path)
    app = criar_app(
        config,
        llm=FakeLLM(),
        banco=banco,
        autenticador=FakeAutenticador(
            {"token-maria": "maria", "token-joao": "joao"}
        ),
    )
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        yield cliente


def _autorizacao(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_sem_token_responde_401(cliente):
    assert (await cliente.get("/pessoas")).status_code == 401
    assert (await cliente.get("/health")).status_code == 200


async def test_token_invalido_responde_401(cliente):
    resposta = await cliente.get(
        "/pessoas", headers=_autorizacao("token-errado")
    )
    assert resposta.status_code == 401


async def test_pessoa_vem_do_sub_do_token(cliente):
    criada = await cliente.post(
        "/pessoas",
        headers=_autorizacao("token-maria"),
        json={"nome": "Maria", "faixa_etaria": "adulto"},
    )
    assert criada.status_code == 201, criada.text
    assert criada.json()["id"] == "maria"

    obtida = await cliente.get(
        "/pessoas/maria", headers=_autorizacao("token-maria")
    )
    assert obtida.status_code == 200

    negada = await cliente.get(
        "/pessoas/joao", headers=_autorizacao("token-maria")
    )
    assert negada.status_code == 403


async def test_chat_nao_aceita_pessoa_id_de_outra_pessoa(cliente):
    await cliente.post(
        "/pessoas",
        headers=_autorizacao("token-maria"),
        json={"nome": "Maria", "faixa_etaria": "adulto"},
    )

    resposta = await cliente.post(
        "/chat",
        headers=_autorizacao("token-maria"),
        json={"pessoa_id": "joao", "mensagem": "oi"},
    )
    assert resposta.status_code == 403


async def test_chat_usa_o_sub_quando_pessoa_id_e_omitido(cliente):
    await cliente.post(
        "/pessoas",
        headers=_autorizacao("token-maria"),
        json={"nome": "Maria", "faixa_etaria": "adulto"},
    )

    resposta = await cliente.post(
        "/chat",
        headers=_autorizacao("token-maria"),
        json={"mensagem": "Oi, Sera"},
    )
    assert resposta.status_code == 200
    nomes = [nome for nome, _ in eventos(resposta.text)]
    assert "done" in nomes


async def test_allowlist_de_email(config):
    from dataclasses import replace

    banco = Banco(config.db_path)
    app = criar_app(
        replace(config, emails_permitidos=("maria@example.com",)),
        llm=FakeLLM(),
        banco=banco,
        autenticador=FakeAutenticador(
            {"token-maria": "maria"}, email="outra@example.com"
        ),
    )
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        resposta = await cliente.get(
            "/pessoas", headers=_autorizacao("token-maria")
        )
        assert resposta.status_code == 403
