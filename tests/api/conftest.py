from pathlib import Path

import httpx
import pytest

from sera.api import Config, criar_app
from tests.api.ajuda import FakeLLM

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def fake() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def config(tmp_path) -> Config:
    return Config(
        db_path=tmp_path / "sera.db",
        personality_path=RAIZ / "personality.yaml",
        llm_base_url="http://fake.local/v1",
        llm_model="fake-model",
    )


@pytest.fixture
def app(config, fake):
    return criar_app(config, llm=fake)


@pytest.fixture
async def cliente(app):
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        yield cliente
