from __future__ import annotations

import json
from typing import AsyncIterator, Mapping, Sequence

from sera.api.llm import Delta, ErroDoProvedor, Fim, Uso


class FakeLLM:
    def __init__(
        self,
        chunks: Sequence[str] = ("Olá", ", ", "Maria!"),
        *,
        falhar_antes: bool = False,
        falhar_apos: int | None = None,
        uso: Uso | None = None,
    ) -> None:
        self.chunks = list(chunks)
        self.falhar_antes = falhar_antes
        self.falhar_apos = falhar_apos
        self.uso = uso
        self.mensagens: list[dict] = []
        self.temperatura: float | None = None
        self.max_tokens: int | None = None

    async def stream(
        self,
        mensagens: Sequence[Mapping[str, str]],
        *,
        temperatura: float,
        max_tokens: int,
    ) -> AsyncIterator[Delta | Fim]:
        self.mensagens = [dict(mensagem) for mensagem in mensagens]
        self.temperatura = temperatura
        self.max_tokens = max_tokens

        if self.falhar_antes:
            raise ErroDoProvedor("falha simulada", status=500)

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
