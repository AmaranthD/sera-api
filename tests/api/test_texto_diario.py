from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
import pytest

from sera.api import agenda, texto_diario
from sera.api.config import Config
from sera.api.ferramentas import ContextoFerramentas, executar_ferramenta
from sera.api.texto_diario import (
    extrair_texto_do_dia,
    formatar_texto_do_dia,
    limpar_cache,
)
from tests.api.ajuda import criar_pessoa

pytestmark = pytest.mark.anyio

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / (
    "texto_diario_2026_11_04.html"
)
URL = "https://wol.jw.org/pt/wol/dt/r5/lp-t/2026/11/4"


def _transporte() -> httpx.MockTransport:
    html = FIXTURE.read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == URL
        return httpx.Response(200, text=html)

    return httpx.MockTransport(handler)


def test_extrai_titulo_tema_corpo_e_links():
    html = FIXTURE.read_text(encoding="utf-8")
    texto = extrair_texto_do_dia(html, dia=date(2026, 11, 4), url=URL)

    assert texto.titulo == "Quarta-feira, 4 de novembro"
    assert "Há mais felicidade em dar do que em receber" in texto.tema
    assert "Atos 20:35" in texto.tema
    assert "servos ministeriais" in texto.corpo
    assert len(texto.links) == 3
    assert all(link.startswith("https://wol.jw.org/") for link in texto.links)

    mensagem = formatar_texto_do_dia(texto)
    assert mensagem.startswith("## Texto diário — Quarta-feira, 4 de novembro")
    assert f"[Ver no JW.org]({URL}#externo)" in mensagem
    assert "(https://wol.jw.org/pt/wol/bc/" in mensagem


async def test_busca_texto_do_dia_na_url_certa():
    limpar_cache()
    texto = await texto_diario.buscar_texto_do_dia(
        date(2026, 11, 4), transporte=_transporte()
    )
    assert texto.titulo == "Quarta-feira, 4 de novembro"


async def test_dispara_uma_vez_por_dia_e_posta_na_conversa(
    config, monkeypatch
):
    limpar_cache()
    config = replace(
        config,
        vapid_public_key="chave-publica",
        vapid_private_key="chave-privada",
    )
    enviados: list[tuple[str, dict]] = []

    async def falso_enviar(inscricao, payload, cfg):
        enviados.append((inscricao["endpoint"], payload))

    monkeypatch.setattr(texto_diario, "enviar_push", falso_enviar)

    from sera.api import criar_app

    app = criar_app(config)
    banco = app.state.banco_admin
    await banco.criar_pessoa("maria", "Maria", "adulto", "padrao")
    await banco.criar_inscricao(
        "maria", "https://push.exemplo/abc", "p", "a", None
    )
    await banco.salvar_assinatura_texto_diario(
        "maria", True, "07:00", "UTC"
    )

    momento = datetime(2026, 11, 4, 8, 0, tzinfo=timezone.utc)
    primeiro = await texto_diario.disparar_textos_diarios(
        banco, config, momento, transporte=_transporte()
    )
    assert primeiro == {"assinaturas": 1, "enviados": 1, "falhas": 0}
    assert len(enviados) == 1
    assert enviados[0][1]["titulo"] == "Texto diário de hoje"
    assert enviados[0][1]["tipo"] == "texto_diario"
    assert "*" not in enviados[0][1]["corpo"]
    assert "](" not in enviados[0][1]["corpo"]
    assert "Atos 20:35" in enviados[0][1]["corpo"]

    assinatura = await banco.obter_assinatura_texto_diario("maria")
    assert assinatura["ultimo_envio_dia"] == "2026-11-04"
    conversa = await banco.obter_conversa(assinatura["conversa_id"])
    assert conversa["titulo"] == "Texto diário"
    mensagens = await banco.listar_mensagens(conversa["id"])
    assert len(mensagens) == 1
    assert mensagens[0]["papel"] == "assistant"
    assert "Atos 20:35" in mensagens[0]["conteudo"]

    segundo = await texto_diario.disparar_textos_diarios(
        banco, config, momento, transporte=_transporte()
    )
    assert segundo == {"assinaturas": 1, "enviados": 0, "falhas": 0}
    assert len(enviados) == 1
    assert len(await banco.listar_mensagens(conversa["id"])) == 1


async def test_nao_dispara_antes_do_horario(config):
    limpar_cache()
    from sera.api import criar_app

    app = criar_app(config)
    banco = app.state.banco_admin
    await banco.criar_pessoa("maria", "Maria", "adulto", "padrao")
    await banco.salvar_assinatura_texto_diario(
        "maria", True, "07:00", "UTC"
    )

    momento = datetime(2026, 11, 4, 6, 59, tzinfo=timezone.utc)
    resultado = await texto_diario.disparar_textos_diarios(
        banco, config, momento, transporte=_transporte()
    )
    assert resultado["enviados"] == 0


async def test_rotas_de_texto_diario(cliente, monkeypatch):
    await criar_pessoa(cliente)

    inicial = await cliente.get("/pessoas/maria/texto-diario")
    assert inicial.status_code == 200
    assert inicial.json()["ativo"] is False

    salvo = await cliente.put(
        "/pessoas/maria/texto-diario",
        json={"ativo": True, "hora": "06:30", "fuso": "UTC"},
    )
    assert salvo.status_code == 200, salvo.text
    assert salvo.json()["ativo"] is True
    assert salvo.json()["hora"] == "06:30"

    invalido = await cliente.put(
        "/pessoas/maria/texto-diario",
        json={"ativo": True, "hora": "25:00"},
    )
    assert invalido.status_code == 422

    fuso_invalido = await cliente.put(
        "/pessoas/maria/texto-diario",
        json={"ativo": True, "hora": "07:00", "fuso": "Marte/Olympus"},
    )
    assert fuso_invalido.status_code == 422


async def test_enviar_agora_e_ferramenta(cliente, app, monkeypatch):
    await criar_pessoa(cliente)

    async def falso_entregar(banco, config, pessoa_id, **kwargs):
        return {
            "conversa_id": "c1",
            "mensagem_id": "m1",
            "dia": "2026-11-04",
            "enviados": 0,
            "falhas": 0,
        }

    monkeypatch.setattr(agenda, "entregar_texto_do_dia", falso_entregar)
    resposta = await cliente.post("/pessoas/maria/texto-diario/enviar")
    assert resposta.status_code == 202, resposta.text
    assert resposta.json()["conversa_id"] == "c1"

    contexto = ContextoFerramentas(
        banco=app.state.banco,
        pessoa_id="maria",
        config=app.state.config,
    )
    ativado = await executar_ferramenta(
        "texto_diario",
        {"acao": "ativar", "hora": "06:30"},
        contexto,
    )
    assert ativado["ok"] is True
    assert ativado["assinatura"]["hora"] == "06:30"

    consultado = await executar_ferramenta(
        "texto_diario", {"acao": "consultar"}, contexto
    )
    assert consultado["assinatura"]["ativo"] is True


async def test_modal_recusa_link_fora_do_jw(cliente, monkeypatch):
    await criar_pessoa(cliente)

    externo = await cliente.get(
        "/jw/conteudo", params={"url": "https://example.com/artigo"}
    )
    assert externo.status_code == 422

    from sera.api import rotas
    from sera.api.jw_conteudo import ConteudoJW

    async def falso_buscar(url):
        return ConteudoJW(
            titulo="Atos 20",
            paragrafos=("texto",),
            url="https://wol.jw.org/pt/wol/bc/r5/lp-t/1/1/0",
        )

    monkeypatch.setattr(rotas, "buscar_conteudo_jw", falso_buscar)
    valido = await cliente.get(
        "/jw/conteudo",
        params={
            "url": "https://wol.jw.org/pt/wol/bc/r5/lp-t/1/1/0"
        },
    )
    assert valido.status_code == 200, valido.text
    assert valido.json()["titulo"] == "Atos 20"
