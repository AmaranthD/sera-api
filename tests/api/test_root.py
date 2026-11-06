import pytest

from sera.api.root import DIAGNOSTICO
from tests.api.ajuda import criar_pessoa, eventos, tokens

pytestmark = pytest.mark.anyio

SENHA = "12345"


@pytest.fixture(autouse=True)
def diagnostico_limpo():
    DIAGNOSTICO.limpar()
    yield
    DIAGNOSTICO.limpar()


async def _pedir_root(cliente) -> str:
    resposta = await cliente.post(
        "/chat", json={"pessoa_id": "maria", "mensagem": "/root"}
    )
    ev = eventos(resposta.text)
    return next(dados for nome, dados in ev if nome == "done")["conversa_id"]


async def test_root_pede_senha_e_mostra_diagnostico(cliente, fake):
    await criar_pessoa(cliente)

    resposta = await cliente.post(
        "/chat", json={"pessoa_id": "maria", "mensagem": "/root"}
    )
    ev = eventos(resposta.text)
    assert "senha" in "".join(tokens(ev)).lower()

    conversa_id = next(dados for nome, dados in ev if nome == "done")[
        "conversa_id"
    ]

    resposta = await cliente.post(
        "/chat",
        json={
            "pessoa_id": "maria",
            "conversa_id": conversa_id,
            "mensagem": SENHA,
        },
    )
    ev = eventos(resposta.text)
    texto = "".join(tokens(ev))
    assert fake.chamadas_recebidas == 0
    assert "Modelo principal" in texto
    assert "fake-model" in texto
    assert "operacional" in texto
    assert "Erros recentes" in texto

    mensagens = await cliente.get(f"/conversas/{conversa_id}/mensagens")
    conteudos = [mensagem["conteudo"] for mensagem in mensagens.json()]
    assert SENHA not in conteudos
    assert "••••••" in conteudos


async def test_root_nao_deixa_a_senha_chegar_ao_modelo(cliente, fake):
    await criar_pessoa(cliente)
    conversa_id = await _pedir_root(cliente)

    await cliente.post(
        "/chat",
        json={
            "pessoa_id": "maria",
            "conversa_id": conversa_id,
            "mensagem": SENHA,
        },
    )

    assert fake.chamadas_recebidas == 0


async def test_root_recusa_senha_errada(cliente, fake):
    await criar_pessoa(cliente)
    conversa_id = await _pedir_root(cliente)

    resposta = await cliente.post(
        "/chat",
        json={
            "pessoa_id": "maria",
            "conversa_id": conversa_id,
            "mensagem": "0000",
        },
    )
    texto = "".join(tokens(eventos(resposta.text)))

    assert "Senha incorreta" in texto
    assert "Modelo principal" not in texto
    assert fake.chamadas_recebidas == 0


async def test_root_sem_pedido_e_mensagem_normal(cliente, fake):
    await criar_pessoa(cliente)

    await cliente.post(
        "/chat", json={"pessoa_id": "maria", "mensagem": "Oi, Sera"}
    )

    assert fake.chamadas_recebidas == 1


async def test_root_funciona_no_job(cliente, fake):
    await criar_pessoa(cliente)

    resposta = await cliente.post(
        "/chat/job", json={"pessoa_id": "maria", "mensagem": "/root"}
    )
    assert resposta.status_code == 202
    trabalho = resposta.json()
    assert trabalho["status"] == "completa"

    resposta = await cliente.post(
        "/chat/job",
        json={
            "pessoa_id": "maria",
            "conversa_id": trabalho["conversa_id"],
            "mensagem": SENHA,
        },
    )
    trabalho = resposta.json()
    assert trabalho["status"] == "completa"

    mensagens = await cliente.get(
        f"/conversas/{trabalho['conversa_id']}/mensagens"
    )
    conteudos = [mensagem["conteudo"] for mensagem in mensagens.json()]
    assert any("Modelo principal" in conteudo for conteudo in conteudos)
    assert SENHA not in conteudos
    assert fake.chamadas_recebidas == 0
