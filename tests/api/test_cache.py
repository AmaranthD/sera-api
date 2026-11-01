import pytest

from tests.api.ajuda import criar_pessoa

pytestmark = pytest.mark.anyio


async def test_api_nao_cacheia_respostas_autenticadas(cliente):
    await criar_pessoa(cliente)

    resposta = await cliente.get("/pessoas")

    assert resposta.status_code == 200
    assert resposta.headers["cache-control"] == "no-store"


async def test_stream_do_chat_mantem_no_cache(cliente):
    await criar_pessoa(cliente)

    resposta = await cliente.post(
        "/chat", json={"pessoa_id": "maria", "mensagem": "oi"}
    )

    assert resposta.status_code == 200
    assert resposta.headers["cache-control"] == "no-cache"
