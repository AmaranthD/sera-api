from dataclasses import replace

import httpx
import pytest

from sera.api import criar_app
from tests.api.ajuda import FakeLLM

pytestmark = pytest.mark.anyio


async def test_tts_desligado_responde_503(config):
    app = criar_app(config, llm=FakeLLM())
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        resposta = await cliente.post("/tts", json={"texto": "Oi"})

    assert resposta.status_code == 503


async def test_tts_devolve_mp3(config, monkeypatch):
    import edge_tts

    class CommunicateFalso:
        def __init__(self, texto, voz, **opcoes):
            self.texto = texto
            self.voz = voz
            self.opcoes = opcoes

        async def stream(self):
            yield {"type": "audio", "data": b"ID3"}
            yield {"type": "audio", "data": b"\x04"}

    monkeypatch.setattr(edge_tts, "Communicate", CommunicateFalso)
    app = criar_app(
        replace(config, tts_habilitado=True, tts_voz="pt-BR-FranciscaNeural"),
        llm=FakeLLM(),
    )
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        resposta = await cliente.post("/tts", json={"texto": "Oi, Sera"})

        info = await cliente.get("/tts")

    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "audio/mpeg"
    assert resposta.content == b"ID3\x04"
    assert info.json() == {
        "disponivel": True,
        "voz": "pt-BR-FranciscaNeural",
    }
