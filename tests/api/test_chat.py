from dataclasses import replace

import httpx
import pytest

from sera.api import Config, criar_app
from tests.api.ajuda import (
    FakeLLM,
    criar_pessoa,
    eventos,
    system_prompt,
    tokens,
)

pytestmark = pytest.mark.anyio


async def test_health(cliente):
    resposta = await cliente.get("/health")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


async def test_streaming_devolve_tokens_e_done(cliente, fake):
    await criar_pessoa(cliente)

    resposta = await cliente.post(
        "/chat", json={"pessoa_id": "maria", "mensagem": "Oi, Sera"}
    )

    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/event-stream")
    ev = eventos(resposta.text)
    assert tokens(ev) == ["Olá", ", ", "Maria!"]

    done = next(dados for nome, dados in ev if nome == "done")
    assert done["conversa_id"]
    assert done["mensagem_id"]
    assert done["modelo"] == "fake-model"
    assert fake.temperatura == 0.8
    assert fake.max_tokens == 1024


async def test_streaming_persiste_pergunta_e_resposta(cliente):
    await criar_pessoa(cliente)
    resposta = await cliente.post(
        "/chat", json={"pessoa_id": "maria", "mensagem": "Oi, Sera"}
    )
    done = next(dados for nome, dados in eventos(resposta.text) if nome == "done")

    mensagens = await cliente.get(
        f"/conversas/{done['conversa_id']}/mensagens"
    )
    assert [m["papel"] for m in mensagens.json()] == ["user", "assistant"]
    assert mensagens.json()[0]["conteudo"] == "Oi, Sera"
    assert mensagens.json()[1]["conteudo"] == "Olá, Maria!"
    assert mensagens.json()[1]["status"] == "completa"


async def test_system_prompt_vai_primeiro(cliente, fake):
    await criar_pessoa(cliente)
    await cliente.post("/chat", json={"pessoa_id": "maria", "mensagem": "Oi"})
    assert fake.mensagens[0]["role"] == "system"
    assert fake.mensagens[0]["content"].startswith("# LIMITES INVIOLÁVEIS")
    assert fake.mensagens[-1] == {"role": "user", "content": "Oi"}


async def test_stream_false_devolve_json(cliente):
    await criar_pessoa(cliente)
    resposta = await cliente.post(
        "/chat",
        json={"pessoa_id": "maria", "mensagem": "Oi", "stream": False},
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["resposta"] == "Olá, Maria!"
    assert corpo["conversa_id"]
    assert corpo["mensagem_id"]


async def test_reutiliza_conversa_e_monta_historico(cliente, fake):
    await criar_pessoa(cliente)
    primeira = await cliente.post(
        "/chat", json={"pessoa_id": "maria", "mensagem": "primeira"}
    )
    done = next(dados for nome, dados in eventos(primeira.text) if nome == "done")

    fake.chunks = ["segunda resposta"]
    await cliente.post(
        "/chat",
        json={
            "pessoa_id": "maria",
            "mensagem": "segunda",
            "conversa_id": done["conversa_id"],
        },
    )

    papeis = [m["role"] for m in fake.mensagens]
    assert papeis == ["system", "user", "assistant", "user"]
    assert fake.mensagens[1]["content"] == "primeira"
    assert fake.mensagens[2]["content"] == "Olá, Maria!"
    assert fake.mensagens[3]["content"] == "segunda"


async def test_conversa_de_outra_pessoa_responde_404(cliente):
    await criar_pessoa(cliente, "maria", "Maria")
    await criar_pessoa(cliente, "joao", "João")
    primeira = await cliente.post(
        "/chat", json={"pessoa_id": "maria", "mensagem": "oi"}
    )
    done = next(dados for nome, dados in eventos(primeira.text) if nome == "done")

    resposta = await cliente.post(
        "/chat",
        json={
            "pessoa_id": "joao",
            "mensagem": "oi",
            "conversa_id": done["conversa_id"],
        },
    )
    assert resposta.status_code == 404


async def test_pessoa_inexistente_responde_404(cliente):
    resposta = await cliente.post(
        "/chat", json={"pessoa_id": "ninguem", "mensagem": "oi"}
    )
    assert resposta.status_code == 404


async def test_memoria_entra_no_system_prompt(cliente, fake):
    await criar_pessoa(cliente)
    await cliente.post(
        "/pessoas/maria/memorias",
        json={"texto": "gosta de jazz", "categoria": "gostos"},
    )
    await cliente.post("/chat", json={"pessoa_id": "maria", "mensagem": "oi"})
    assert "gosta de jazz" in system_prompt(fake)
    assert "[gostos]" in system_prompt(fake)


async def test_memoria_nao_vaza_entre_pessoas(cliente, fake):
    await criar_pessoa(cliente, "maria", "Maria")
    await criar_pessoa(cliente, "joao", "João")
    await cliente.post(
        "/pessoas/maria/memorias", json={"texto": "gosta de jazz"}
    )
    await cliente.post("/chat", json={"pessoa_id": "joao", "mensagem": "oi"})
    assert "gosta de jazz" not in system_prompt(fake)


async def test_ajuste_entra_no_system_prompt(cliente, fake):
    await criar_pessoa(cliente)
    await cliente.post(
        "/pessoas/maria/ajustes",
        json={"tipo": "apelido", "texto": "chama ela de Mãe Sera"},
    )
    await cliente.post("/chat", json={"pessoa_id": "maria", "mensagem": "oi"})
    assert "chama ela de Mãe Sera" in system_prompt(fake)


async def test_nao_mencionar_silencia_fato(cliente, fake):
    await criar_pessoa(cliente)
    await cliente.post(
        "/pessoas/maria/memorias",
        json={"texto": "passou por uma separação difícil"},
    )
    await cliente.post(
        "/pessoas/maria/nao_mencionar", json={"tema": "separação"}
    )
    await cliente.post("/chat", json={"pessoa_id": "maria", "mensagem": "oi"})
    prompt = system_prompt(fake)
    assert "passou por uma separação difícil" not in prompt
    assert "Tópicos que não devem ser trazidos à conversa: separação." in prompt


async def test_falha_antes_do_primeiro_token_responde_502(cliente, fake):
    await criar_pessoa(cliente)
    fake.falhar_antes = True

    streaming = await cliente.post(
        "/chat", json={"pessoa_id": "maria", "mensagem": "oi"}
    )
    assert streaming.status_code == 502

    unico = await cliente.post(
        "/chat",
        json={"pessoa_id": "maria", "mensagem": "oi", "stream": False},
    )
    assert unico.status_code == 502


async def test_falha_no_meio_emite_error_e_salva_parcial(cliente, fake):
    await criar_pessoa(cliente)
    fake.chunks = ["Olá", " mundo"]
    fake.falhar_apos = 1

    resposta = await cliente.post(
        "/chat", json={"pessoa_id": "maria", "mensagem": "oi"}
    )
    ev = eventos(resposta.text)
    assert tokens(ev) == ["Olá"]
    assert ev[-1][0] == "error"
    assert ev[-1][1]["codigo"] == "llm_falhou"

    conversas = await cliente.get("/pessoas/maria/conversas")
    conversa_id = conversas.json()[0]["id"]
    mensagens = await cliente.get(f"/conversas/{conversa_id}/mensagens")
    assistente = mensagens.json()[-1]
    assert assistente["status"] == "erro"
    assert assistente["conteudo"] == "Olá"


async def test_parcial_com_erro_nao_entra_no_historico(cliente, fake):
    await criar_pessoa(cliente)
    fake.chunks = ["Olá", " mundo"]
    fake.falhar_apos = 1
    await cliente.post("/chat", json={"pessoa_id": "maria", "mensagem": "oi"})

    conversa_id = (await cliente.get("/pessoas/maria/conversas")).json()[0]["id"]
    fake.falhar_apos = None
    fake.chunks = ["certo"]
    await cliente.post(
        "/chat",
        json={
            "pessoa_id": "maria",
            "mensagem": "de novo",
            "conversa_id": conversa_id,
        },
    )

    assert [m["role"] for m in fake.mensagens] == ["system", "user", "user"]
    assert "mundo" not in " ".join(
        m["content"] for m in fake.mensagens if m["role"] != "system"
    )


async def test_janela_de_historico(config, fake):
    app = criar_app(replace(config, max_history_mensagens=2), llm=fake)
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        await criar_pessoa(cliente)
        primeira = await cliente.post(
            "/chat", json={"pessoa_id": "maria", "mensagem": "primeira"}
        )
        conversa_id = next(
            dados for nome, dados in eventos(primeira.text) if nome == "done"
        )["conversa_id"]

        fake.chunks = ["r2"]
        await cliente.post(
            "/chat",
            json={
                "pessoa_id": "maria",
                "mensagem": "segunda",
                "conversa_id": conversa_id,
            },
        )
        fake.chunks = ["r3"]
        await cliente.post(
            "/chat",
            json={
                "pessoa_id": "maria",
                "mensagem": "terceira",
                "conversa_id": conversa_id,
            },
        )

        assert [m["role"] for m in fake.mensagens] == [
            "system",
            "user",
            "assistant",
            "user",
        ]
        assert fake.mensagens[1]["content"] == "segunda"
        assert fake.mensagens[3]["content"] == "terceira"

