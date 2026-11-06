from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from sera.api import Config, criar_app
from sera.api.busca import BuscaIndisponivel, ResultadoBusca
from sera.api.llm import ChamadaFerramenta
from sera.api.relogio import normalizar_consulta
from tests.api.ajuda import (
    FakeBusca,
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


async def test_streaming_comeca_com_start(cliente):
    await criar_pessoa(cliente)

    resposta = await cliente.post(
        "/chat", json={"pessoa_id": "maria", "mensagem": "Oi, Sera"}
    )
    ev = eventos(resposta.text)

    assert ev[0][0] == "start"
    start = ev[0][1]
    done = next(dados for nome, dados in ev if nome == "done")
    assert start["conversa_id"] == done["conversa_id"]
    assert start["mensagem_id"]

    mensagens = await cliente.get(
        f"/conversas/{start['conversa_id']}/mensagens"
    )
    assert mensagens.json()[0]["id"] == start["mensagem_id"]


async def test_titulo_da_conversa_vem_da_primeira_mensagem(cliente):
    await criar_pessoa(cliente)
    mensagem = "  Quero   conversar sobre o almoço de domingo com a família  "

    await cliente.post(
        "/chat", json={"pessoa_id": "maria", "mensagem": mensagem}
    )
    conversas = await cliente.get("/pessoas/maria/conversas")

    assert conversas.json()[0]["titulo"] == (
        "Quero conversar sobre o almoço de domingo com a família"
    )


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


async def test_falha_antes_do_primeiro_token_emite_error_no_stream(
    cliente, fake
):
    await criar_pessoa(cliente)
    fake.falhar_antes = True

    streaming = await cliente.post(
        "/chat", json={"pessoa_id": "maria", "mensagem": "oi"}
    )
    # O `start` já saiu; a falha do provedor vira evento, não status HTTP.
    assert streaming.status_code == 200
    ev = eventos(streaming.text)
    assert ev[0][0] == "start"
    assert ev[-1][0] == "error"
    assert ev[-1][1]["codigo"] == "llm_falhou"

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


def _config_com_busca(config: Config) -> Config:
    return replace(
        config,
        llm_provider="openai",
        busca_habilitada=True,
        tavily_api_key="tvly-teste",
        busca_max_resultados=3,
    )


def _resultados_busca() -> list[ResultadoBusca]:
    return [
        ResultadoBusca(
            titulo="Previsão do tempo",
            url="https://exemplo.com/tempo",
            trecho="Sol com algumas nuvens, 30 °C.",
        )
    ]


async def _cliente_com_busca(config, fake, busca):
    app = criar_app(_config_com_busca(config), llm=fake, busca=busca)
    transporte = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transporte, base_url="http://test")


async def test_busca_desligada_nao_passa_ferramentas(cliente, fake):
    await criar_pessoa(cliente)
    await cliente.post(
        "/chat",
        json={"pessoa_id": "maria", "mensagem": "pesquise o dólar hoje"},
    )
    nomes = {item["function"]["name"] for item in (fake.ferramentas or [])}
    assert "pesquisar_web" not in nomes
    # O aprendizado continua disponível mesmo com a busca desligada.
    assert {"lembrar", "ajustar_preferencia"} <= nomes


async def test_ferramentas_de_assunto_so_entram_quando_pedidas(cliente, fake):
    await criar_pessoa(cliente)
    await cliente.post(
        "/chat", json={"pessoa_id": "maria", "mensagem": "Oi, Sera"}
    )
    nomes = {item["function"]["name"] for item in (fake.ferramentas or [])}
    assert "agendar" not in nomes
    assert "texto_diario" not in nomes
    assert "jw" not in nomes

    await cliente.post(
        "/chat",
        json={"pessoa_id": "maria", "mensagem": "Agende uma consulta amanhã"},
    )
    nomes = {item["function"]["name"] for item in (fake.ferramentas or [])}
    assert "agendar" in nomes


async def test_pesquisa_explicita_consulta_antes_do_modelo(config, fake):
    busca = FakeBusca(_resultados_busca())
    async with await _cliente_com_busca(config, fake, busca) as cliente:
        await criar_pessoa(cliente)
        resposta = await cliente.post(
            "/chat",
            json={
                "pessoa_id": "maria",
                "mensagem": "pesquise a previsão do tempo em São Paulo",
            },
        )

    assert busca.consultas == ["a previsão do tempo em São Paulo"]
    assert "Resultados da busca na internet" in system_prompt(fake)
    assert "https://exemplo.com/tempo" in system_prompt(fake)
    # A busca já foi feita; a ferramenta de pesquisa não é oferecida de novo.
    nomes = {item["function"]["name"] for item in (fake.ferramentas or [])}
    assert "pesquisar_web" not in nomes
    assert "lembrar" in nomes

    ev = eventos(resposta.text)
    fontes = [dados for nome, dados in ev if nome == "sources"]
    assert fontes[0]["fontes"][0]["url"] == "https://exemplo.com/tempo"


async def test_modelo_decide_pesquisar_por_tool_call(config, fake):
    busca = FakeBusca(_resultados_busca())
    fake.chamadas = [
        ChamadaFerramenta(
            id="call_1",
            nome="pesquisar_web",
            argumentos='{"consulta": "dólar hoje"}',
        )
    ]
    fake.chunks = ["O dólar está em alta (https://exemplo.com/dolar)."]

    async with await _cliente_com_busca(config, fake, busca) as cliente:
        await criar_pessoa(cliente)
        resposta = await cliente.post(
            "/chat",
            json={"pessoa_id": "maria", "mensagem": "quanto está o dólar hoje?"},
        )

    assert busca.consultas == [
        normalizar_consulta(
            "dólar hoje",
            datetime.now(ZoneInfo("America/Sao_Paulo")),
        )
    ]
    assert fake.chamadas_recebidas == 2
    assert "https://exemplo.com/tempo" in system_prompt(fake)
    assert fake.mensagens[-1]["role"] == "user"

    ev = eventos(resposta.text)
    assert any(nome == "tool" for nome, _ in ev)
    assert any(nome == "sources" for nome, _ in ev)
    assert tokens(ev) == ["O dólar está em alta (https://exemplo.com/dolar)."]


async def test_busca_falhando_nao_quebra_o_chat(config, fake):
    busca = FakeBusca(erro=BuscaIndisponivel("fora do ar"))
    async with await _cliente_com_busca(config, fake, busca) as cliente:
        await criar_pessoa(cliente)
        resposta = await cliente.post(
            "/chat",
            json={"pessoa_id": "maria", "mensagem": "pesquise o dólar"},
        )

    assert resposta.status_code == 200
    assert "A busca falhou agora" in system_prompt(fake)
    assert tokens(eventos(resposta.text)) == ["Olá", ", ", "Maria!"]


async def test_system_prompt_inclui_data_e_hora(cliente, fake):
    await criar_pessoa(cliente)
    await cliente.post("/chat", json={"pessoa_id": "maria", "mensagem": "Oi"})

    prompt = system_prompt(fake)
    hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y")
    assert "# AGORA" in prompt
    assert f'"hoje" = {hoje}' in prompt
    assert "Nunca diga que não sabe a data de hoje" in prompt


async def test_modelo_pode_lembrar_no_chat(cliente, fake):
    await criar_pessoa(cliente)
    fake.chamadas = [
        ChamadaFerramenta(
            id="call_1",
            nome="lembrar",
            argumentos='{"texto": "Gosta de jazz", "categoria": "gostos"}',
        )
    ]
    fake.chunks = ["Anotado."]

    resposta = await cliente.post(
        "/chat",
        json={"pessoa_id": "maria", "mensagem": "lembre que eu gosto de jazz"},
    )

    assert fake.chamadas_recebidas == 2
    assert tokens(eventos(resposta.text)) == ["Anotado."]
    assert "Guardei na memória: Gosta de jazz." in system_prompt(fake)

    memorias = await cliente.get("/pessoas/maria/memorias")
    assert [item["texto"] for item in memorias.json()] == ["Gosta de jazz"]


async def test_pedido_explicito_de_esquecer_apaga_antes_do_modelo(cliente, fake):
    await criar_pessoa(cliente)
    await cliente.post(
        "/pessoas/maria/memorias",
        json={"texto": "Gosta de jazz", "categoria": "gostos"},
    )
    fake.chunks = ["Esqueci."]

    resposta = await cliente.post(
        "/chat",
        json={"pessoa_id": "maria", "mensagem": "esqueça que eu gosto de jazz"},
    )

    assert tokens(eventos(resposta.text)) == ["Esqueci."]
    assert "Esqueci: Gosta de jazz." in system_prompt(fake)
    assert (await cliente.get("/pessoas/maria/memorias")).json() == []
    nomes = {item["function"]["name"] for item in (fake.ferramentas or [])}
    assert "esquecer" not in nomes


async def test_nao_esqueca_nao_apaga_memoria(cliente, fake):
    await criar_pessoa(cliente)
    await cliente.post(
        "/pessoas/maria/memorias",
        json={"texto": "Gosta de jazz", "categoria": "gostos"},
    )

    await cliente.post(
        "/chat",
        json={
            "pessoa_id": "maria",
            "mensagem": "não esqueça de comprar leite",
        },
    )

    memorias = await cliente.get("/pessoas/maria/memorias")
    assert [item["texto"] for item in memorias.json()] == ["Gosta de jazz"]


async def test_saude_so_grava_com_sim_explicito(cliente, fake):
    await criar_pessoa(cliente)
    chamada = ChamadaFerramenta(
        id="call_1",
        nome="lembrar",
        argumentos=(
            '{"texto": "Tem diabetes", "categoria": "saude", '
            '"confirmado": true}'
        ),
    )

    fake.chamadas = [chamada]
    await cliente.post(
        "/chat",
        json={"pessoa_id": "maria", "mensagem": "tenho diabetes"},
    )
    assert (await cliente.get("/pessoas/maria/memorias")).json() == []

    fake.chamadas = [chamada]
    await cliente.post(
        "/chat",
        json={"pessoa_id": "maria", "mensagem": "sim, pode guardar"},
    )
    memorias = await cliente.get("/pessoas/maria/memorias")
    assert [item["texto"] for item in memorias.json()] == ["Tem diabetes"]



