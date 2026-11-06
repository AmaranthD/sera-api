import asyncio
from dataclasses import replace

import httpx
import pytest

from sera.api import criar_app
from tests.api.ajuda import FakeBusca, FakeLLM, criar_pessoa

pytestmark = pytest.mark.anyio


async def _aguardar(cliente, conversa_id: str, resposta_id: str):
    for _ in range(250):
        resposta = await cliente.get(f"/conversas/{conversa_id}/mensagens")
        assert resposta.status_code == 200, resposta.text
        lista = resposta.json()
        mensagem = next(
            (item for item in lista if item["id"] == resposta_id), None
        )
        if mensagem is not None and mensagem["status"] != "gerando":
            return lista, mensagem
        await asyncio.sleep(0.02)
    raise AssertionError("o job não terminou a tempo")


async def test_job_devolve_ids_e_completa_a_resposta(cliente, fake):
    await criar_pessoa(cliente)

    inicio = await cliente.post(
        "/chat/job", json={"pessoa_id": "maria", "mensagem": "Oi, Sera"}
    )

    assert inicio.status_code == 202, inicio.text
    trabalho = inicio.json()
    assert trabalho["status"] == "gerando"
    assert trabalho["conversa_id"]
    assert trabalho["mensagem_id"]
    assert trabalho["resposta_id"]

    lista, mensagem = await _aguardar(
        cliente, trabalho["conversa_id"], trabalho["resposta_id"]
    )

    assert [item["papel"] for item in lista] == ["user", "assistant"]
    assert lista[0]["conteudo"] == "Oi, Sera"
    assert mensagem["conteudo"] == "Olá, Maria!"
    assert mensagem["status"] == "completa"
    assert mensagem["fontes"] == []


async def test_job_nao_duplica_mensagem_do_usuario(cliente, fake):
    await criar_pessoa(cliente)
    inicio = await cliente.post(
        "/chat/job", json={"pessoa_id": "maria", "mensagem": "Oi, Sera"}
    )
    trabalho = inicio.json()
    await _aguardar(cliente, trabalho["conversa_id"], trabalho["resposta_id"])

    usuarios = [item for item in fake.mensagens if item["role"] == "user"]
    assert [item["content"] for item in usuarios] == ["Oi, Sera"]


async def test_job_persiste_fontes_da_busca(config, fake):
    from sera.api import Config
    from sera.api.busca import ResultadoBusca

    assert isinstance(config, Config)
    busca = FakeBusca(
        [
            ResultadoBusca(
                titulo="Cotação",
                url="https://exemplo.com/dolar",
                trecho="R$ 5,40",
            )
        ]
    )
    app = criar_app(
        replace(
            config,
            busca_habilitada=True,
            tavily_api_key="tvly-teste",
        ),
        llm=fake,
        busca=busca,
    )
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        await criar_pessoa(cliente)
        inicio = await cliente.post(
            "/chat/job",
            json={
                "pessoa_id": "maria",
                "mensagem": "pesquise o dólar hoje",
            },
        )
        trabalho = inicio.json()
        _, mensagem = await _aguardar(
            cliente, trabalho["conversa_id"], trabalho["resposta_id"]
        )

    assert mensagem["status"] == "completa"
    assert mensagem["fontes"][0]["url"] == "https://exemplo.com/dolar"


async def test_job_marca_erro_quando_provedor_falha(config):
    fake = FakeLLM(falhar_antes=True)
    app = criar_app(config, llm=fake)
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        await criar_pessoa(cliente)
        inicio = await cliente.post(
            "/chat/job", json={"pessoa_id": "maria", "mensagem": "Oi"}
        )
        trabalho = inicio.json()
        _, mensagem = await _aguardar(
            cliente, trabalho["conversa_id"], trabalho["resposta_id"]
        )

    assert mensagem["status"] == "erro"


async def test_job_pode_ser_cancelado(config):
    fake = FakeLLM(chunks=["a", "b", "c"], pausa=0.5)
    app = criar_app(config, llm=fake)
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        await criar_pessoa(cliente)
        inicio = await cliente.post(
            "/chat/job", json={"pessoa_id": "maria", "mensagem": "Oi"}
        )
        trabalho = inicio.json()

        cancelamento = await cliente.post(
            f"/chat/job/{trabalho['resposta_id']}/cancelar"
        )
        assert cancelamento.status_code == 204

        _, mensagem = await _aguardar(
            cliente, trabalho["conversa_id"], trabalho["resposta_id"]
        )

    assert mensagem["status"] == "interrompida"


async def test_job_recusa_segundo_enquanto_gera(config):
    fake = FakeLLM(chunks=["a"], pausa=0.5)
    app = criar_app(config, llm=fake)
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        await criar_pessoa(cliente)
        primeiro = await cliente.post(
            "/chat/job", json={"pessoa_id": "maria", "mensagem": "Oi"}
        )
        trabalho = primeiro.json()

        segundo = await cliente.post(
            "/chat/job",
            json={
                "pessoa_id": "maria",
                "mensagem": "De novo",
                "conversa_id": trabalho["conversa_id"],
            },
        )
        assert segundo.status_code == 409

        await cliente.post(
            f"/chat/job/{trabalho['resposta_id']}/cancelar"
        )
        await _aguardar(
            cliente, trabalho["conversa_id"], trabalho["resposta_id"]
        )


async def test_gerando_orfao_vira_interrompida(cliente, app):
    await criar_pessoa(cliente)
    banco = app.state.banco
    conversa = await banco.criar_conversa("maria", "órfã")
    mensagem = await banco.criar_mensagem(
        conversa["id"], "assistant", "", "gerando"
    )

    resposta = await cliente.get(
        f"/conversas/{conversa['id']}/mensagens"
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo[0]["id"] == mensagem["id"]
    assert corpo[0]["status"] == "interrompida"


async def test_dois_pedidos_simultaneos_na_mesma_conversa(config):
    fake = FakeLLM(chunks=["a"], pausa=0.5)
    app = criar_app(config, llm=fake)
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        await criar_pessoa(cliente)
        conversa = await app.state.banco.criar_conversa("maria", "corrida")
        corpo = {
            "pessoa_id": "maria",
            "mensagem": "Oi",
            "conversa_id": conversa["id"],
        }

        primeiro, segundo = await asyncio.gather(
            cliente.post("/chat/job", json=corpo),
            cliente.post("/chat/job", json=corpo),
        )

        assert sorted([primeiro.status_code, segundo.status_code]) == [
            202,
            409,
        ]
        trabalho = (
            primeiro.json()
            if primeiro.status_code == 202
            else segundo.json()
        )
        await cliente.post(f"/chat/job/{trabalho['resposta_id']}/cancelar")
        await _aguardar(cliente, conversa["id"], trabalho["resposta_id"])

        mensagens = await app.state.banco.listar_mensagens(conversa["id"])
        assert [item["papel"] for item in mensagens] == ["user", "assistant"]


async def test_encerrar_jobs_marca_resposta_interrompida(config):
    fake = FakeLLM(chunks=["a", "b", "c"], pausa=0.5)
    app = criar_app(config, llm=fake)
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        await criar_pessoa(cliente)
        inicio = await cliente.post(
            "/chat/job", json={"pessoa_id": "maria", "mensagem": "Oi"}
        )
        trabalho = inicio.json()

        await app.state.jobs.encerrar()

        mensagem = await app.state.banco.obter_mensagem(
            trabalho["resposta_id"]
        )

    assert mensagem["status"] == "interrompida"


async def test_estado_job_devolve_a_resposta(cliente):
    await criar_pessoa(cliente)
    inicio = await cliente.post(
        "/chat/job", json={"pessoa_id": "maria", "mensagem": "Oi, Sera"}
    )
    trabalho = inicio.json()
    await _aguardar(cliente, trabalho["conversa_id"], trabalho["resposta_id"])

    resposta = await cliente.get(f"/chat/job/{trabalho['resposta_id']}")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["id"] == trabalho["resposta_id"]
    assert corpo["status"] == "completa"
    assert corpo["conteudo"] == "Olá, Maria!"


async def test_estado_job_resolve_orfao(cliente, app):
    await criar_pessoa(cliente)
    banco = app.state.banco
    conversa = await banco.criar_conversa("maria", "órfã")
    mensagem = await banco.criar_mensagem(
        conversa["id"], "assistant", "", "gerando"
    )

    resposta = await cliente.get(f"/chat/job/{mensagem['id']}")

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "interrompida"


async def test_job_envia_push_quando_resposta_fica_pronta(
    config, fake, monkeypatch
):
    from dataclasses import replace

    from sera.api import rotas as rotas_mod

    envios: list[dict] = []

    async def push_falso(inscricao, payload, config):
        envios.append({"inscricao": inscricao, "payload": payload})

    monkeypatch.setattr(rotas_mod, "enviar_push", push_falso)
    app = criar_app(
        replace(
            config,
            vapid_public_key="chave-publica",
            vapid_private_key="chave-privada",
        ),
        llm=fake,
    )
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        await criar_pessoa(cliente)
        await app.state.banco.criar_inscricao(
            "maria",
            "https://push.exemplo/abc",
            "p256dh",
            "auth",
        )
        inicio = await cliente.post(
            "/chat/job",
            json={"pessoa_id": "maria", "mensagem": "Oi, Sera"},
        )
        trabalho = inicio.json()
        await _aguardar(
            cliente, trabalho["conversa_id"], trabalho["resposta_id"]
        )
        for _ in range(100):
            if envios:
                break
            await asyncio.sleep(0.02)

    assert len(envios) == 1
    payload = envios[0]["payload"]
    assert payload["tipo"] == "mensagem"
    assert payload["corpo"] == "Sua resposta está pronta."
    assert payload["url"] == f"/c/{trabalho['conversa_id']}"
    assert payload["tag"] == f"chat-{trabalho['resposta_id']}"


async def test_job_ignora_agendamentos_duplicados(config, fake):
    from sera.api.llm import ChamadaFerramenta

    argumentos = (
        '{"titulo": "Consulta", "inicio": "2026-11-25T09:00", '
        '"fim": "2026-11-25T10:00"}'
    )
    fake.chamadas = [
        ChamadaFerramenta(id="a", nome="agendar", argumentos=argumentos),
        ChamadaFerramenta(id="b", nome="agendar", argumentos=argumentos),
    ]
    fake.chunks = ["Agendado."]
    app = criar_app(config, llm=fake)
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        await criar_pessoa(cliente)
        inicio = await cliente.post(
            "/chat/job",
            json={
                "pessoa_id": "maria",
                "mensagem": "Agende uma consulta dia 25 às 9",
            },
        )
        trabalho = inicio.json()
        _, mensagem = await _aguardar(
            cliente, trabalho["conversa_id"], trabalho["resposta_id"]
        )

    compromissos = await app.state.banco.listar_compromissos(
        "maria", None, None
    )
    assert mensagem["status"] == "completa"
    assert [item["titulo"] for item in compromissos] == ["Consulta"]
