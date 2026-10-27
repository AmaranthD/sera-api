import sqlite3

import pytest

from tests.api.ajuda import criar_pessoa, eventos

pytestmark = pytest.mark.anyio


def _contar(app, tabela: str) -> int:
    conexao = sqlite3.connect(app.state.config.db_path)
    try:
        return conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
    finally:
        conexao.close()


async def test_crud_de_pessoa(cliente):
    await criar_pessoa(cliente)

    obtida = await cliente.get("/pessoas/maria")
    assert obtida.status_code == 200
    assert obtida.json()["nome"] == "Maria"
    assert obtida.json()["faixa_etaria"] == "adulto"

    listadas = await cliente.get("/pessoas")
    assert [p["id"] for p in listadas.json()] == ["maria"]

    duplicada = await cliente.post(
        "/pessoas",
        json={
            "id": "maria",
            "nome": "Outra",
            "faixa_etaria": "adulto",
        },
    )
    assert duplicada.status_code == 409

    invalida = await cliente.post(
        "/pessoas",
        json={"id": "Maria!", "nome": "X", "faixa_etaria": "adulto"},
    )
    assert invalida.status_code == 422


async def test_crud_de_memoria(cliente):
    await criar_pessoa(cliente)

    criada = await cliente.post(
        "/pessoas/maria/memorias",
        json={"texto": "tem um gato chamado Tobias", "categoria": "familia"},
    )
    assert criada.status_code == 201
    memoria_id = criada.json()["id"]

    listadas = await cliente.get("/pessoas/maria/memorias")
    assert [m["texto"] for m in listadas.json()] == ["tem um gato chamado Tobias"]

    apagada = await cliente.delete(f"/pessoas/maria/memorias/{memoria_id}")
    assert apagada.status_code == 204
    assert (await cliente.get("/pessoas/maria/memorias")).json() == []

    denovo = await cliente.delete(f"/pessoas/maria/memorias/{memoria_id}")
    assert denovo.status_code == 404


async def test_memoria_com_segredo_e_recusada(cliente):
    await criar_pessoa(cliente)
    resposta = await cliente.post(
        "/pessoas/maria/memorias",
        json={"texto": "a senha do Wi-Fi é 1234"},
    )
    assert resposta.status_code == 422


async def test_crud_de_tema_silenciado(cliente):
    await criar_pessoa(cliente)

    criado = await cliente.post(
        "/pessoas/maria/nao_mencionar", json={"tema": "separação"}
    )
    assert criado.status_code == 201

    duplicado = await cliente.post(
        "/pessoas/maria/nao_mencionar", json={"tema": "separação"}
    )
    assert duplicado.status_code == 409

    assert (await cliente.get("/pessoas/maria/nao_mencionar")).json() == [
        "separação"
    ]

    removido = await cliente.delete("/pessoas/maria/nao_mencionar/separação")
    assert removido.status_code == 204
    assert (await cliente.get("/pessoas/maria/nao_mencionar")).json() == []


async def test_crud_de_ajuste(cliente):
    await criar_pessoa(cliente)

    criado = await cliente.post(
        "/pessoas/maria/ajustes",
        json={"tipo": "apelido", "texto": "chama ela de Mãe Sera"},
    )
    assert criado.status_code == 201
    ajuste_id = criado.json()["id"]

    listados = await cliente.get("/pessoas/maria/ajustes")
    assert listados.json()[0]["texto"] == "chama ela de Mãe Sera"
    assert listados.json()[0]["origem"] == "manual"

    sem_valor = await cliente.post(
        "/pessoas/maria/ajustes", json={"tipo": "nivel_sarcasmo"}
    )
    assert sem_valor.status_code == 422

    valor_invalido = await cliente.post(
        "/pessoas/maria/ajustes",
        json={"tipo": "nivel_sarcasmo", "valor": "extremo"},
    )
    assert valor_invalido.status_code == 422

    apagado = await cliente.delete(f"/pessoas/maria/ajustes/{ajuste_id}")
    assert apagado.status_code == 204
    assert (await cliente.get("/pessoas/maria/ajustes")).json() == []


async def test_apagar_pessoa_apaga_tudo(app, cliente):
    await criar_pessoa(cliente)
    await cliente.post(
        "/pessoas/maria/memorias", json={"texto": "gosta de jazz"}
    )
    await cliente.post(
        "/pessoas/maria/nao_mencionar", json={"tema": "trabalho"}
    )
    resposta = await cliente.post(
        "/chat", json={"pessoa_id": "maria", "mensagem": "oi"}
    )
    assert any(nome == "done" for nome, _ in eventos(resposta.text))

    assert _contar(app, "conversas") == 1
    assert _contar(app, "mensagens") == 2

    apagada = await cliente.delete("/pessoas/maria")
    assert apagada.status_code == 204

    assert _contar(app, "pessoas") == 0
    assert _contar(app, "conversas") == 0
    assert _contar(app, "mensagens") == 0
    assert _contar(app, "memorias") == 0
    assert _contar(app, "nao_mencionar") == 0


async def test_conversas_e_mensagens(cliente):
    await criar_pessoa(cliente)
    resposta = await cliente.post(
        "/chat", json={"pessoa_id": "maria", "mensagem": "oi"}
    )
    conversa_id = next(
        dados for nome, dados in eventos(resposta.text) if nome == "done"
    )["conversa_id"]

    conversas = await cliente.get("/pessoas/maria/conversas")
    assert conversas.status_code == 200
    assert conversas.json()[0]["id"] == conversa_id

    mensagens = await cliente.get(f"/conversas/{conversa_id}/mensagens")
    assert mensagens.status_code == 200
    assert [m["status"] for m in mensagens.json()] == ["completa", "completa"]

    assert (
        await cliente.get("/conversas/nao-existe/mensagens")
    ).status_code == 404
