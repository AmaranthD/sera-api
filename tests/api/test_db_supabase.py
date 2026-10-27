import json
from pathlib import Path

import httpx
import pytest

from sera.api import Config
from sera.api.db_supabase import BancoSupabase, Conflito

pytestmark = pytest.mark.anyio

RAIZ = Path(__file__).resolve().parents[2]


def _config() -> Config:
    return Config(
        personality_path=RAIZ / "personality.yaml",
        supabase_url="https://fake.supabase.co",
        supabase_anon_key="anon-key",
    )


def _banco(handler) -> BancoSupabase:
    return BancoSupabase(
        _config(), "token-do-usuario", transporte=httpx.MockTransport(handler)
    )


async def test_criar_pessoa_usa_jwt_e_devolve_linha():
    chamadas: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(request)
        return httpx.Response(
            201,
            json=[
                {
                    "id": "11111111-1111-4111-8111-111111111111",
                    "nome": "Maria",
                    "faixa_etaria": "adulto",
                }
            ],
        )

    banco = _banco(handler)
    try:
        pessoa = await banco.criar_pessoa(
            "11111111-1111-4111-8111-111111111111",
            "Maria",
            "adulto",
            "padrao",
            True,
        )
    finally:
        await banco.fechar()

    assert pessoa["nome"] == "Maria"
    requisicao = chamadas[0]
    assert requisicao.method == "POST"
    assert requisicao.url.path == "/rest/v1/pessoas"
    assert requisicao.headers["authorization"] == "Bearer token-do-usuario"
    assert requisicao.headers["apikey"] == "anon-key"
    corpo = json.loads(requisicao.content)
    assert corpo["id"] == "11111111-1111-4111-8111-111111111111"
    assert corpo["acesso_vault"] is True


async def test_obter_pessoa_inexistente_devolve_none():
    banco = _banco(lambda request: httpx.Response(200, json=[]))
    try:
        assert await banco.obter_pessoa("x") is None
    finally:
        await banco.fechar()


async def test_tema_duplicado_devolve_false():
    banco = _banco(
        lambda request: httpx.Response(
            409, json={"code": "23505", "message": "duplicate key"}
        )
    )
    try:
        assert await banco.adicionar_tema("pessoa", "tema") is False
    finally:
        await banco.fechar()


async def test_conflito_de_unicidade_em_pessoa():
    banco = _banco(
        lambda request: httpx.Response(
            409, json={"code": "23505", "message": "duplicate key"}
        )
    )
    try:
        with pytest.raises(Conflito):
            await banco.criar_pessoa(
                "11111111-1111-4111-8111-111111111111",
                "Maria",
                "adulto",
                "padrao",
                True,
            )
    finally:
        await banco.fechar()


async def test_buscar_trechos_chama_rpc():
    chamadas: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(request)
        return httpx.Response(
            200, json=[{"nota": "Saúde", "secao": "Rotina", "texto": "..."}]
        )

    banco = _banco(handler)
    try:
        trechos = await banco.buscar_trechos("saúde", 3)
    finally:
        await banco.fechar()

    assert trechos[0]["nota"] == "Saúde"
    assert chamadas[0].url.path == "/rest/v1/rpc/buscar_trechos"
    assert json.loads(chamadas[0].content) == {
        "consulta": "saúde",
        "limite": 3,
    }


async def test_criar_mensagem_atualiza_conversa():
    chamadas: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(request)
        if request.method == "POST":
            return httpx.Response(
                201,
                json=[
                    {
                        "id": "m1",
                        "conversa_id": "c1",
                        "papel": "user",
                        "conteudo": "oi",
                        "status": "completa",
                    }
                ],
            )
        return httpx.Response(204)

    banco = _banco(handler)
    try:
        mensagem = await banco.criar_mensagem("c1", "user", "oi")
    finally:
        await banco.fechar()

    assert mensagem["id"] == "m1"
    assert [c.method for c in chamadas] == ["POST", "PATCH"]
    assert chamadas[1].url.path == "/rest/v1/conversas"
    assert chamadas[1].url.params["id"] == "eq.c1"
