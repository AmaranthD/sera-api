from __future__ import annotations

import json
from typing import AsyncIterator, Mapping, Sequence

from sera.api.busca import ResultadoBusca
from sera.api.jw import RespostaJW
from sera.api.llm import (
    ChamadaFerramenta,
    Delta,
    ErroDoProvedor,
    Ferramenta,
    Fim,
    Uso,
)


class FakeJW:
    def __init__(self, texto: str = "Matthew (40)", *, erro=None) -> None:
        self.texto = texto
        self.erro = erro
        self.chamadas: list[tuple[str, dict]] = []

    async def executar(self, ferramenta: str, argumentos=None):
        self.chamadas.append((ferramenta, dict(argumentos or {})))
        if self.erro is not None:
            raise self.erro
        return RespostaJW(ferramenta=ferramenta, texto=self.texto)


class FakeBusca:
    def __init__(
        self,
        resultados: Sequence[ResultadoBusca] | None = None,
        *,
        erro: Exception | None = None,
    ) -> None:
        self.resultados = list(resultados or [])
        self.erro = erro
        self.consultas: list[str] = []

    async def pesquisar(self, consulta: str) -> list[ResultadoBusca]:
        self.consultas.append(consulta)
        if self.erro is not None:
            raise self.erro
        return list(self.resultados)


class FakeLLM:
    def __init__(
        self,
        chunks: Sequence[str] = ("Olá", ", ", "Maria!"),
        *,
        falhar_antes: bool = False,
        falhar_apos: int | None = None,
        uso: Uso | None = None,
        chamadas: Sequence[ChamadaFerramenta] = (),
    ) -> None:
        self.chunks = list(chunks)
        self.falhar_antes = falhar_antes
        self.falhar_apos = falhar_apos
        self.uso = uso
        self.chamadas = list(chamadas)
        self.mensagens: list[dict] = []
        self.temperatura: float | None = None
        self.max_tokens: int | None = None
        self.ferramentas: list[dict] | None = None
        self.escolha_ferramenta: str | None = None
        self.chamadas_recebidas = 0

    async def stream(
        self,
        mensagens: Sequence[Mapping[str, str]],
        *,
        temperatura: float,
        max_tokens: int,
        ferramentas: Sequence[Mapping] | None = None,
        escolha_ferramenta: str | None = None,
    ) -> AsyncIterator[Delta | Ferramenta | Fim]:
        self.mensagens = [dict(mensagem) for mensagem in mensagens]
        self.temperatura = temperatura
        self.max_tokens = max_tokens
        self.ferramentas = list(ferramentas) if ferramentas else None
        self.escolha_ferramenta = escolha_ferramenta
        self.chamadas_recebidas += 1

        if self.falhar_antes:
            raise ErroDoProvedor("falha simulada", status=500)

        if self.chamadas:
            pendentes = self.chamadas
            self.chamadas = []
            yield Ferramenta(tuple(pendentes))
            yield Fim(self.uso)
            return

        for indice, chunk in enumerate(self.chunks):
            if self.falhar_apos is not None and indice >= self.falhar_apos:
                raise ErroDoProvedor("falha simulada no meio", status=500)
            yield Delta(chunk)

        yield Fim(self.uso)


async def criar_pessoa(
    cliente,
    pessoa_id: str = "maria",
    nome: str = "Maria",
    faixa_etaria: str = "adulto",
    perfil: str = "padrao",
) -> dict:
    resposta = await cliente.post(
        "/pessoas",
        json={
            "id": pessoa_id,
            "nome": nome,
            "faixa_etaria": faixa_etaria,
            "perfil": perfil,
        },
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def eventos(texto: str) -> list[tuple[str, dict]]:
    saida: list[tuple[str, dict]] = []
    for bloco in texto.split("\n\n"):
        if not bloco.strip():
            continue
        nome = None
        dados = None
        for linha in bloco.splitlines():
            if linha.startswith("event: "):
                nome = linha[len("event: ") :]
            elif linha.startswith("data: "):
                dados = json.loads(linha[len("data: ") :])
        if nome is not None:
            saida.append((nome, dados or {}))
    return saida


def tokens(ev: list[tuple[str, dict]]) -> list[str]:
    return [dados["texto"] for nome, dados in ev if nome == "token"]


def system_prompt(fake: FakeLLM) -> str:
    return next(
        mensagem["content"]
        for mensagem in fake.mensagens
        if mensagem["role"] == "system"
    )
