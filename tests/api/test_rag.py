from __future__ import annotations

import httpx
import pytest

from sera.api import Config, criar_app
from sera.api.db import Banco
from sera.rag import iterar_notas
from tests.api.ajuda import FakeLLM, eventos, system_prompt

pytestmark = pytest.mark.anyio

NOTAS = {
    "Projetos/Seraphine.md": (
        "---\ntags:\n  - projeto\n  - ia\n---\n\n"
        "# Seraphine\n\nAssistente pessoal de IA com memória.\n\n"
        "## Visão\n\nRAG sobre as notas do vault.\n"
    ),
    "Estudos/Saude.md": (
        "# Saúde\n\n## Rotina\n\nCaminhada de manhã e água ao longo do dia.\n"
    ),
    "Templates/Modelo.md": "# Modelo\n\nnão deve entrar no índice.\n",
}


@pytest.fixture
def notas(tmp_path):
    raiz = tmp_path / "Notes"
    for caminho, texto in NOTAS.items():
        arquivo = raiz / caminho
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(texto, encoding="utf-8")
    return raiz


@pytest.fixture
def banco(tmp_path, notas):
    banco = Banco(tmp_path / "sera.db")
    banco.iniciar()
    return banco


@pytest.fixture
def config(tmp_path, notas):
    from pathlib import Path

    return Config(
        db_path=tmp_path / "sera.db",
        personality_path=Path(__file__).resolve().parents[2]
        / "personality.yaml",
        llm_base_url="http://fake.local/v1",
        llm_model="fake-model",
        notas_path=notas,
        max_trechos_contexto=3,
    )


@pytest.fixture
async def api(config, banco):
    fake = FakeLLM()
    app = criar_app(config, llm=fake)
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://test"
    ) as cliente:
        yield cliente, fake


async def conversar(cliente, pessoa_id="maria", mensagem="sobre o que é a Sera?"):
    resposta = await cliente.post(
        "/chat", json={"pessoa_id": pessoa_id, "mensagem": mensagem}
    )
    assert resposta.status_code == 200, resposta.text
    assert eventos(resposta.text)


async def criar(cliente, pessoa_id="maria", **extra):
    corpo = {
        "id": pessoa_id,
        "nome": "Maria",
        "faixa_etaria": "adulto",
        "perfil": "padrao",
    }
    corpo.update(extra)
    resposta = await cliente.post("/pessoas", json=corpo)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


async def test_busca_encontra_nota_por_termo(banco):
    await banco.indexar_notas(list(iterar_notas(_raiz(banco))))
    trechos = await banco.buscar_trechos("rag vault", 3)
    assert {trecho["nota"] for trecho in trechos} == {"Seraphine"}


async def test_busca_ignora_acentos(banco):
    await banco.indexar_notas(list(iterar_notas(_raiz(banco))))
    assert {t["nota"] for t in await banco.buscar_trechos("saude", 3)} == {
        "Saúde"
    }
    assert {t["nota"] for t in await banco.buscar_trechos("saúde", 3)} == {
        "Saúde"
    }


async def test_busca_sem_termo_util_nao_retorna_nada(banco):
    await banco.indexar_notas(list(iterar_notas(_raiz(banco))))
    assert await banco.buscar_trechos("!!!", 3) == []
    assert await banco.buscar_trechos("", 3) == []


async def test_indexacao_e_incremental(banco):
    notas = list(iterar_notas(_raiz(banco)))
    primeiro = await banco.indexar_notas(notas)
    segundo = await banco.indexar_notas(notas)
    assert primeiro["notas_novas"] == 2
    assert segundo["notas_novas"] == 0
    assert segundo["trechos_indexados"] == 0


async def test_indexacao_remove_nota_apagada(banco, notas):
    await banco.indexar_notas(list(iterar_notas(notas)))
    (notas / "Estudos" / "Saude.md").unlink()
    resultado = await banco.indexar_notas(list(iterar_notas(notas)))
    assert resultado["notas_removidas"] == 1
    assert await banco.buscar_trechos("caminhada", 3) == []


async def test_chat_com_acesso_inclui_trechos(api, banco):
    cliente, fake = api
    await banco.indexar_notas(list(iterar_notas(_raiz(banco))))
    await criar(cliente)

    await conversar(cliente)

    prompt = system_prompt(fake)
    assert "# TRECHOS DAS NOTAS" in prompt
    assert "### [[Seraphine]]" in prompt
    assert "RAG sobre as notas do vault." in prompt


async def test_chat_sem_acesso_nao_inclui_trechos(api, banco):
    cliente, fake = api
    await banco.indexar_notas(list(iterar_notas(_raiz(banco))))
    await criar(cliente, "bia", faixa_etaria="crianca")

    await conversar(cliente, "bia")

    assert "# TRECHOS DAS NOTAS" not in system_prompt(fake)


async def test_acesso_ao_vault_pode_ser_forcado(api, banco):
    cliente, fake = api
    await banco.indexar_notas(list(iterar_notas(_raiz(banco))))
    await criar(cliente, "bia", faixa_etaria="crianca", acesso_vault=True)

    await conversar(cliente, "bia")

    assert "# TRECHOS DAS NOTAS" in system_prompt(fake)


async def test_sem_indice_nao_quebra_o_chat(api):
    cliente, fake = api
    await criar(cliente)

    await conversar(cliente)

    assert "# TRECHOS DAS NOTAS" not in system_prompt(fake)


async def test_templates_ficam_fora_do_indice(banco):
    await banco.indexar_notas(list(iterar_notas(_raiz(banco))))
    assert await banco.buscar_trechos("modelo", 3) == []


def _raiz(banco):
    from pathlib import Path

    return Path(banco.caminho).parent / "Notes"
