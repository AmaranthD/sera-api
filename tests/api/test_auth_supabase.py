import httpx
import pytest
from fastapi import HTTPException

from sera.api import Config
from sera.api.auth import AutenticadorSupabase

pytestmark = pytest.mark.anyio

TOKEN_MALFORMADO = "abc.def.ghi"


def _config() -> Config:
    return Config(
        llm_base_url="http://fake.local/v1",
        llm_model="fake-model",
        supabase_url="https://fake.supabase.co",
        supabase_anon_key="anon",
        auth_required=True,
    )


def _autenticador(handler) -> AutenticadorSupabase:
    transporte = httpx.MockTransport(handler)
    return AutenticadorSupabase(
        _config(), cliente=httpx.AsyncClient(transport=transporte)
    )


@pytest.mark.parametrize("status", [401, 403])
async def test_token_recusado_pelo_supabase_responde_401(status):
    autenticador = _autenticador(
        lambda request: httpx.Response(status, json={"msg": "invalid JWT"})
    )

    with pytest.raises(HTTPException) as erro:
        await autenticador.validar(TOKEN_MALFORMADO)

    assert erro.value.status_code == 401
    assert erro.value.headers == {"WWW-Authenticate": "Bearer"}


async def test_erro_do_supabase_responde_503():
    autenticador = _autenticador(
        lambda request: httpx.Response(500, text="boom")
    )

    with pytest.raises(HTTPException) as erro:
        await autenticador.validar(TOKEN_MALFORMADO)

    assert erro.value.status_code == 503


async def test_falha_de_rede_responde_503():
    def handler(request):
        raise httpx.ConnectError("sem rota", request=request)

    autenticador = _autenticador(handler)

    with pytest.raises(HTTPException) as erro:
        await autenticador.validar(TOKEN_MALFORMADO)

    assert erro.value.status_code == 503


async def test_introspeccao_valida_extrai_sub_e_email():
    autenticador = _autenticador(
        lambda request: httpx.Response(
            200, json={"id": "pessoa-1", "email": "maria@example.com"}
        )
    )

    usuario = await autenticador.validar(TOKEN_MALFORMADO)

    assert usuario.id == "pessoa-1"
    assert usuario.email == "maria@example.com"
    assert usuario.token == TOKEN_MALFORMADO
