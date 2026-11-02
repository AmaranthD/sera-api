from dataclasses import replace

import httpx
import pytest

from sera.api import criar_app

pytestmark = pytest.mark.anyio


async def test_cors_libera_patch_para_o_front(config, fake):
    app = criar_app(
        replace(config, cors_origins=("https://app.test",)), llm=fake
    )
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        resposta = await cliente.options(
            "/pessoas/maria/memorias/mem-1",
            headers={
                "Origin": "https://app.test",
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

    assert resposta.status_code == 200
    assert "PATCH" in resposta.headers["access-control-allow-methods"]
    assert resposta.headers["access-control-allow-origin"] == "https://app.test"


REGEX_PAGES = r"^https://([a-z0-9-]+\.)?sera-chat\.pages\.dev$"


async def test_cors_regex_so_libera_o_projeto_sera_chat(config, fake):
    app = criar_app(
        replace(config, cors_origin_regex=REGEX_PAGES), llm=fake
    )
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        for origem in (
            "https://sera-chat.pages.dev",
            "https://preview.sera-chat.pages.dev",
        ):
            resposta = await cliente.options(
                "/pessoas/maria/memorias/mem-1",
                headers={
                    "Origin": origem,
                    "Access-Control-Request-Method": "PATCH",
                },
            )
            assert (
                resposta.headers.get("access-control-allow-origin")
                == origem
            )

        intrusa = await cliente.options(
            "/pessoas/maria/memorias/mem-1",
            headers={
                "Origin": "https://outro.pages.dev",
                "Access-Control-Request-Method": "PATCH",
            },
        )
        assert "access-control-allow-origin" not in intrusa.headers
