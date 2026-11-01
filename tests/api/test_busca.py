import json

import httpx
import pytest

from sera.api.busca import BuscaIndisponivel, ClienteTavily
from sera.api.config import Config

pytestmark = pytest.mark.anyio


def _config(**kwargs) -> Config:
    base = {
        "tavily_api_key": "tvly-teste",
        "busca_habilitada": True,
        "busca_max_resultados": 3,
    }
    base.update(kwargs)
    return Config(**base)


def _resposta_tavily() -> dict:
    return {
        "query": "dólar hoje",
        "results": [
            {
                "title": "Cotação do dólar",
                "url": "https://exemplo.com/dolar",
                "content": "Dólar fechou em R$ 5,40.",
                "score": 0.9,
            },
            {
                "title": "Sem URL válida",
                "url": "",
                "content": "ignorar",
            },
            {
                "title": "Notícia",
                "url": "https://exemplo.com/noticia",
                "content": "Outro resultado",
                "published_date": "2026-10-31",
            },
        ],
    }


async def test_consulta_tavily_e_normaliza_resultados():
    pedidos: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.tavily.com/search"
        assert request.headers["authorization"] == "Bearer tvly-teste"
        pedidos.append(json.loads(request.read()))
        return httpx.Response(200, json=_resposta_tavily())

    cliente = ClienteTavily(_config(), transporte=httpx.MockTransport(handler))
    resultados = await cliente.pesquisar("  dólar   hoje ")

    assert [r.url for r in resultados] == [
        "https://exemplo.com/dolar",
        "https://exemplo.com/noticia",
    ]
    assert resultados[0].titulo == "Cotação do dólar"
    assert resultados[1].data == "2026-10-31"
    assert pedidos[0]["query"] == "dólar hoje"
    assert pedidos[0]["max_results"] == 3
    assert pedidos[0]["country"] == "brazil"
    assert pedidos[0]["include_raw_content"] is False


async def test_cache_evita_segunda_chamada():
    chamadas = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal chamadas
        chamadas += 1
        return httpx.Response(200, json=_resposta_tavily())

    cliente = ClienteTavily(_config(), transporte=httpx.MockTransport(handler))
    await cliente.pesquisar("dólar hoje")
    await cliente.pesquisar("DÓLAR HOJE")

    assert chamadas == 1


async def test_cache_expira():
    chamadas = 0
    agora = [0.0]

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal chamadas
        chamadas += 1
        return httpx.Response(200, json=_resposta_tavily())

    cliente = ClienteTavily(
        _config(busca_cache_ttl=10),
        transporte=httpx.MockTransport(handler),
        relogio=lambda: agora[0],
    )
    await cliente.pesquisar("dólar hoje")
    agora[0] = 11
    await cliente.pesquisar("dólar hoje")

    assert chamadas == 2


async def test_erro_429_vira_busca_indisponivel():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="limite")

    cliente = ClienteTavily(_config(), transporte=httpx.MockTransport(handler))
    with pytest.raises(BuscaIndisponivel) as capturado:
        await cliente.pesquisar("dólar")
    assert capturado.value.status == 429


async def test_timeout_vira_busca_indisponivel():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("demorou", request=request)

    cliente = ClienteTavily(_config(), transporte=httpx.MockTransport(handler))
    with pytest.raises(BuscaIndisponivel, match="timeout"):
        await cliente.pesquisar("dólar")


async def test_json_invalido_vira_busca_indisponivel():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>erro</html>")

    cliente = ClienteTavily(_config(), transporte=httpx.MockTransport(handler))
    with pytest.raises(BuscaIndisponivel, match="JSON"):
        await cliente.pesquisar("dólar")


async def test_sem_chave_recusa_antes_da_rede():
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("não deveria chamar a rede")

    cliente = ClienteTavily(
        _config(tavily_api_key=None), transporte=httpx.MockTransport(handler)
    )
    with pytest.raises(BuscaIndisponivel, match="TAVILY_API_KEY"):
        await cliente.pesquisar("dólar")


async def test_consulta_vazia_nao_chama_api():
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("não deveria chamar a rede")

    cliente = ClienteTavily(_config(), transporte=httpx.MockTransport(handler))
    assert await cliente.pesquisar("  ") == []
