from dataclasses import replace
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from sera.api import criar_app
from sera.api import agenda
from sera.api.webpush import FalhaPush
from tests.api.ajuda import criar_pessoa

pytestmark = pytest.mark.anyio

MARIA = "/pessoas/maria/compromissos"


def _iso(delta_minutos: int) -> str:
    instante = datetime.now(timezone.utc) + timedelta(minutes=delta_minutos)
    return instante.isoformat(timespec="seconds")


async def _criar(cliente, **mudancas):
    corpo = {
        "titulo": "Consulta",
        "inicio": "2026-11-10T14:00:00-03:00",
        "fim": "2026-11-10T15:00:00-03:00",
        "lembrete_minutos": 10,
    }
    corpo.update(mudancas)
    return await cliente.post(MARIA, json=corpo)


async def test_cria_lista_atualiza_e_apaga(cliente):
    await criar_pessoa(cliente)
    criado = await _criar(cliente, descricao="Levar exames")
    assert criado.status_code == 201, criado.text
    compromisso = criado.json()
    assert compromisso["titulo"] == "Consulta"
    assert compromisso["fuso"] == "America/Sao_Paulo"
    assert compromisso["inicio"].endswith("+00:00")
    assert compromisso["lembrete_em"] < compromisso["inicio"]

    lista = await cliente.get(MARIA)
    assert lista.status_code == 200
    assert [item["id"] for item in lista.json()] == [compromisso["id"]]

    atualizado = await cliente.patch(
        f"{MARIA}/{compromisso['id']}",
        json={"titulo": "Consulta médica"},
    )
    assert atualizado.status_code == 200
    assert atualizado.json()["titulo"] == "Consulta médica"

    apagado = await cliente.delete(f"{MARIA}/{compromisso['id']}")
    assert apagado.status_code == 204
    assert (await cliente.get(MARIA)).json() == []


async def test_recusa_sobreposicao_do_mesmo_usuario(cliente):
    await criar_pessoa(cliente)
    assert (await _criar(cliente)).status_code == 201

    conflito = await _criar(
        cliente,
        titulo="Dentista",
        inicio="2026-11-10T14:30:00-03:00",
        fim="2026-11-10T15:30:00-03:00",
    )

    assert conflito.status_code == 409
    assert "Consulta" in conflito.json()["detail"]


async def test_horarios_encostados_nao_conflitam(cliente):
    await criar_pessoa(cliente)
    assert (await _criar(cliente)).status_code == 201

    seguinte = await _criar(
        cliente,
        titulo="Reunião",
        inicio="2026-11-10T15:00:00-03:00",
        fim="2026-11-10T16:00:00-03:00",
    )

    assert seguinte.status_code == 201


async def test_sobreposicao_entre_pessoas_e_permitida(cliente):
    await criar_pessoa(cliente)
    await criar_pessoa(cliente, pessoa_id="joao", nome="João")

    assert (await _criar(cliente)).status_code == 201
    outro = await cliente.post(
        "/pessoas/joao/compromissos",
        json={
            "titulo": "Consulta",
            "inicio": "2026-11-10T14:00:00-03:00",
            "fim": "2026-11-10T15:00:00-03:00",
        },
    )
    assert outro.status_code == 201


async def test_atualizacao_ignora_o_proprio_compromisso(cliente):
    await criar_pessoa(cliente)
    compromisso = (await _criar(cliente)).json()

    atualizado = await cliente.patch(
        f"{MARIA}/{compromisso['id']}",
        json={"fim": "2026-11-10T16:00:00-03:00"},
    )

    assert atualizado.status_code == 200
    assert datetime.fromisoformat(atualizado.json()["fim"]) == datetime.fromisoformat(
        "2026-11-10T19:00:00+00:00"
    )


async def test_valida_intervalo_e_fuso(cliente):
    await criar_pessoa(cliente)

    invertido = await _criar(
        cliente,
        inicio="2026-11-10T16:00:00-03:00",
        fim="2026-11-10T15:00:00-03:00",
    )
    assert invertido.status_code == 422

    sem_fuso = await _criar(
        cliente,
        inicio="2026-11-10T14:00:00",
        fim="2026-11-10T15:00:00",
    )
    assert sem_fuso.status_code == 422

    fuso_errado = await _criar(cliente, fuso="Marte/Olympus")
    assert fuso_errado.status_code == 422


async def test_notificacoes_desligadas_sem_vapid(cliente):
    await criar_pessoa(cliente)
    assert (await cliente.get("/notificacoes/chave")).status_code == 503


async def test_inscricao_push_e_teste(config, monkeypatch):
    config = replace(
        config,
        vapid_public_key="chave-publica",
        vapid_private_key="chave-privada",
    )
    app = criar_app(config)
    enviados: list[tuple[str, dict]] = []

    async def falso_enviar(inscricao, payload, cfg):
        enviados.append((inscricao["endpoint"], payload))

    monkeypatch.setattr(agenda, "enviar_push", falso_enviar)

    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        await criar_pessoa(cliente)
        chave = await cliente.get("/notificacoes/chave")
        assert chave.json() == {"chave": "chave-publica"}

        criada = await cliente.post(
            "/pessoas/maria/notificacoes/inscricoes",
            json={
                "endpoint": "https://push.exemplo/abc",
                "keys": {"p256dh": "p", "auth": "a"},
                "user_agent": "teste",
            },
        )
        assert criada.status_code == 201, criada.text

        resposta = await cliente.post(
            "/pessoas/maria/notificacoes/teste"
        )
        assert resposta.status_code == 200
        assert resposta.json()["enviados"] == 1
        assert enviados[0][0] == "https://push.exemplo/abc"

        removida = await cliente.delete(
            "/pessoas/maria/notificacoes/inscricoes",
            params={"endpoint": "https://push.exemplo/abc"},
        )
        assert removida.status_code == 204


async def test_disparo_reivindica_e_remove_inscricao_morta(
    config, monkeypatch
):
    config = replace(
        config,
        vapid_public_key="chave-publica",
        vapid_private_key="chave-privada",
        notificacoes_segredo="segredo",
    )
    app = criar_app(config)
    chamadas: list[str] = []

    async def morta(inscricao, payload, cfg):
        chamadas.append(inscricao["endpoint"])
        raise FalhaPush("gone", status=410)

    monkeypatch.setattr(agenda, "enviar_push", morta)

    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        await criar_pessoa(cliente)
        await cliente.post(
            "/pessoas/maria/notificacoes/inscricoes",
            json={
                "endpoint": "https://push.exemplo/morta",
                "keys": {"p256dh": "p", "auth": "a"},
            },
        )
        criado = await _criar(
            cliente,
            inicio=_iso(-5),
            fim=_iso(55),
            lembrete_minutos=10,
        )
        assert criado.status_code == 201

        primeiro = await agenda.disparar_lembretes(
            app.state.banco_admin, config
        )
        assert primeiro["enviados"] == 0
        assert primeiro["falhas"] == 1
        assert chamadas == ["https://push.exemplo/morta"]

        segundos = await agenda.disparar_lembretes(
            app.state.banco_admin, config
        )
        assert segundos["pendentes"] == 0

        inscricoes = await app.state.banco.listar_inscricoes("maria")
        assert inscricoes == []


async def test_disparo_exige_segredo(config):
    config = replace(
        config,
        vapid_public_key="chave-publica",
        vapid_private_key="chave-privada",
        notificacoes_segredo="segredo",
    )
    app = criar_app(config)
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        negado = await cliente.post("/notificacoes/disparar")
        assert negado.status_code == 401

        errado = await cliente.post(
            "/notificacoes/disparar",
            headers={"X-Sera-Segredo": "outro"},
        )
        assert errado.status_code == 401

        aceito = await cliente.post(
            "/notificacoes/disparar",
            headers={"X-Sera-Segredo": "segredo"},
        )
        assert aceito.status_code == 200


async def test_editar_titulo_nao_reenvia_lembrete(config, monkeypatch):
    config = replace(
        config,
        vapid_public_key="chave-publica",
        vapid_private_key="chave-privada",
    )
    app = criar_app(config)
    enviados: list[str] = []

    async def falso_enviar(inscricao, payload, cfg):
        enviados.append(payload["corpo"])

    monkeypatch.setattr(agenda, "enviar_push", falso_enviar)

    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        await criar_pessoa(cliente)
        await cliente.post(
            "/pessoas/maria/notificacoes/inscricoes",
            json={
                "endpoint": "https://push.exemplo/um",
                "keys": {"p256dh": "p", "auth": "a"},
            },
        )
        criado = (
            await _criar(
                cliente, inicio=_iso(-5), fim=_iso(55), lembrete_minutos=10
            )
        ).json()
        await agenda.disparar_lembretes(app.state.banco_admin, config)
        assert len(enviados) == 1

        await cliente.patch(
            f"{MARIA}/{criado['id']}", json={"titulo": "Novo título"}
        )
        await agenda.disparar_lembretes(app.state.banco_admin, config)
        assert len(enviados) == 1

        await cliente.patch(
            f"{MARIA}/{criado['id']}", json={"inicio": _iso(-1)}
        )
        await agenda.disparar_lembretes(app.state.banco_admin, config)
        assert len(enviados) == 2


def test_validar_chaves_rejeita_privada_em_formato_errado(config):
    import base64
    from dataclasses import replace

    from sera.api.webpush import validar_chaves

    publica = base64.urlsafe_b64encode(b"\x04" + b"\x00" * 64).decode().rstrip("=")
    with pytest.raises(ValueError, match="VAPID_PRIVATE_KEY"):
        validar_chaves(
            replace(
                config,
                vapid_public_key=publica,
                vapid_private_key="chave-privada-em-pem",
            )
        )
