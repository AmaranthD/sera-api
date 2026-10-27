from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, AsyncIterator, Mapping, Protocol, Sequence

import anyio
import httpx

from .config import Config

try:
    from google.genai import errors as _gemini_errors
except ImportError:
    _gemini_errors = None


@dataclass(frozen=True)
class Delta:
    texto: str


@dataclass(frozen=True)
class Uso:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class Fim:
    uso: Uso | None = None


Evento = Delta | Fim


class ErroDoProvedor(Exception):
    def __init__(
        self,
        detalhe: str,
        *,
        status: int | None = None,
        retentavel: bool = False,
        codigo: str = "http",
    ) -> None:
        super().__init__(detalhe)
        self.detalhe = detalhe
        self.status = status
        self.retentavel = retentavel
        self.codigo = codigo


class ClienteLLM(Protocol):
    def stream(
        self,
        mensagens: Sequence[Mapping[str, str]],
        *,
        temperatura: float,
        max_tokens: int,
    ) -> AsyncIterator[Evento]: ...


class ClienteGemini:
    def __init__(self, config: Config, *, cliente: Any | None = None) -> None:
        self._config = config
        if cliente is None:
            try:
                from google import genai
            except ImportError as erro:
                raise RuntimeError(
                    "instale google-genai para usar o provedor gemini"
                ) from erro
            if not config.gemini_api_key:
                raise ValueError(
                    "GEMINI_API_KEY é obrigatória para o provedor gemini"
                )
            cliente = genai.Client(api_key=config.gemini_api_key)
        self._cliente = cliente

    async def stream(
        self,
        mensagens: Sequence[Mapping[str, str]],
        *,
        temperatura: float,
        max_tokens: int,
    ) -> AsyncIterator[Evento]:
        tentativas = 0
        while True:
            emitido = False
            try:
                async for evento in self._tentativa(
                    mensagens, temperatura, max_tokens
                ):
                    if isinstance(evento, Delta):
                        emitido = True
                    yield evento
                return
            except ErroDoProvedor as erro:
                if emitido or not erro.retentavel or tentativas >= 1:
                    raise
                tentativas += 1
                await anyio.sleep(0.5)

    async def _tentativa(
        self,
        mensagens: Sequence[Mapping[str, str]],
        temperatura: float,
        max_tokens: int,
    ) -> AsyncIterator[Evento]:
        sistema, entrada = _converter_para_gemini(mensagens)
        uso: Uso | None = None
        emitiu_texto = False

        corpo: dict[str, Any] = {
            "model": self._config.llm_model,
            "input": entrada,
            "stream": True,
            "store": False,
            "generation_config": {
                "temperature": temperatura,
                "max_output_tokens": max_tokens,
            },
        }
        if sistema:
            corpo["system_instruction"] = sistema

        try:
            fluxo = await self._cliente.aio.interactions.create(**corpo)
            async with fluxo:
                async for evento in fluxo:
                    tipo = getattr(evento, "event_type", "")
                    if tipo == "step.delta":
                        delta = getattr(evento, "delta", None)
                        if getattr(delta, "type", None) == "text":
                            texto = getattr(delta, "text", "") or ""
                            if texto:
                                emitiu_texto = True
                                yield Delta(texto)
                    elif tipo == "step.stop":
                        uso = _uso_gemini(getattr(evento, "usage", None)) or uso
                    elif tipo == "interaction.completed":
                        interacao = getattr(evento, "interaction", None)
                        uso = _uso_gemini(getattr(interacao, "usage", None)) or uso
                        if not emitiu_texto:
                            texto = _texto_da_interacao(interacao)
                            if texto:
                                emitiu_texto = True
                                yield Delta(texto)
                    elif tipo == "error":
                        raise ErroDoProvedor(
                            "Gemini retornou erro: "
                            f"{_descrever(getattr(evento, 'error', None))}",
                            codigo="gemini",
                        )
        except Exception as erro:
            if _gemini_errors is not None and isinstance(
                erro, _gemini_errors.APIError
            ):
                raise _traduzir_erro_gemini(erro) from erro
            raise

        yield Fim(uso)


class ClienteOpenAICompat:
    def __init__(
        self,
        config: Config,
        *,
        transporte: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config
        self._transporte = transporte

    async def stream(
        self,
        mensagens: Sequence[Mapping[str, str]],
        *,
        temperatura: float,
        max_tokens: int,
    ) -> AsyncIterator[Evento]:
        incluir_uso = True
        tentativas = 0
        while True:
            emitido = False
            try:
                async for evento in self._tentativa(
                    mensagens, temperatura, max_tokens, incluir_uso
                ):
                    if isinstance(evento, Delta):
                        emitido = True
                    yield evento
                return
            except ErroDoProvedor as erro:
                if erro.codigo == "stream_options" and incluir_uso:
                    incluir_uso = False
                    continue
                if emitido or not erro.retentavel or tentativas >= 1:
                    raise
                tentativas += 1
                await anyio.sleep(0.5)

    async def _tentativa(
        self,
        mensagens: Sequence[Mapping[str, str]],
        temperatura: float,
        max_tokens: int,
        incluir_uso: bool,
    ) -> AsyncIterator[Evento]:
        config = self._config
        payload: dict = {
            "model": config.llm_model,
            "messages": [dict(mensagem) for mensagem in mensagens],
            "stream": True,
            "temperature": temperatura,
            "max_tokens": max_tokens,
        }
        if incluir_uso:
            payload["stream_options"] = {"include_usage": True}

        cabecalhos = {
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
        }
        if config.llm_api_key:
            cabecalhos["Authorization"] = f"Bearer {config.llm_api_key}"

        timeout = httpx.Timeout(
            config.read_timeout,
            connect=config.connect_timeout,
            write=30.0,
            pool=30.0,
        )
        url = config.url_chat
        uso: Uso | None = None

        try:
            async with httpx.AsyncClient(
                timeout=timeout, transport=self._transporte
            ) as cliente:
                async with cliente.stream(
                    "POST", url, json=payload, headers=cabecalhos
                ) as resposta:
                    if resposta.status_code >= 400:
                        corpo = (await resposta.aread()).decode("utf-8", "replace")
                        codigo = (
                            "stream_options"
                            if resposta.status_code == 400
                            and "stream_options" in corpo
                            else "http"
                        )
                        raise ErroDoProvedor(
                            f"provedor respondeu {resposta.status_code}: "
                            f"{corpo[:300]}",
                            status=resposta.status_code,
                            retentavel=(
                                resposta.status_code == 429
                                or resposta.status_code >= 500
                            ),
                            codigo=codigo,
                        )

                    tipo = resposta.headers.get("content-type", "").lower()
                    if "application/json" in tipo or tipo.endswith("+json"):
                        corpo = (await resposta.aread()).decode("utf-8", "replace")
                        try:
                            bruto = json.loads(corpo)
                        except json.JSONDecodeError as erro:
                            raise ErroDoProvedor(
                                "resposta não é SSE nem JSON válido: "
                                f"{corpo[:300]}",
                                codigo="formato",
                            ) from erro
                        if not isinstance(bruto, Mapping):
                            raise ErroDoProvedor(
                                "resposta JSON inesperada do provedor",
                                codigo="formato",
                            )
                        if bruto.get("error"):
                            raise ErroDoProvedor(
                                "provedor retornou erro: "
                                f"{_mensagem_de_erro(bruto['error'])}",
                                codigo="provedor",
                            )
                        texto = _texto_da_resposta(bruto)
                        if texto:
                            yield Delta(texto)
                        bruto_uso = bruto.get("usage")
                        yield Fim(_uso_de(bruto_uso) if bruto_uso else None)
                        return

                    async for linha in resposta.aiter_lines():
                        if not linha.startswith("data:"):
                            continue
                        dado = linha[5:].strip()
                        if not dado or dado == "[DONE]":
                            continue
                        try:
                            evento = json.loads(dado)
                        except json.JSONDecodeError:
                            continue

                        if evento.get("error"):
                            raise ErroDoProvedor(
                                f"provedor retornou erro: "
                                f"{_mensagem_de_erro(evento['error'])}",
                                codigo="provedor",
                            )
                        if evento.get("usage"):
                            uso = _uso_de(evento["usage"])

                        for escolha in evento.get("choices") or []:
                            delta = escolha.get("delta") or {}
                            texto = delta.get("content")
                            if texto:
                                yield Delta(texto)
        except httpx.TimeoutException as erro:
            raise ErroDoProvedor(
                f"timeout ao falar com o provedor: {erro}",
                codigo="timeout",
                retentavel=True,
            ) from erro
        except httpx.RequestError as erro:
            raise ErroDoProvedor(
                f"falha de rede ao falar com o provedor: {erro}",
                codigo="rede",
                retentavel=True,
            ) from erro

        yield Fim(uso)


def _converter_para_gemini(
    mensagens: Sequence[Mapping[str, str]],
) -> tuple[str, list[dict]]:
    sistema: list[str] = []
    passos: list[dict] = []
    for mensagem in mensagens:
        papel = mensagem.get("role")
        conteudo = mensagem.get("content") or ""
        if papel == "system":
            sistema.append(conteudo)
        elif papel == "user":
            passos.append(
                {
                    "type": "user_input",
                    "content": [{"type": "text", "text": conteudo}],
                }
            )
        elif papel == "assistant":
            passos.append(
                {
                    "type": "model_output",
                    "content": [{"type": "text", "text": conteudo}],
                }
            )
    return "\n\n".join(sistema).strip(), passos


def _texto_da_interacao(interacao: Any) -> str:
    texto = getattr(interacao, "output_text", None)
    if texto:
        return texto
    partes: list[str] = []
    for passo in getattr(interacao, "steps", None) or []:
        if getattr(passo, "type", None) != "model_output":
            continue
        for conteudo in getattr(passo, "content", None) or []:
            if getattr(conteudo, "type", None) == "text":
                partes.append(getattr(conteudo, "text", "") or "")
    return "".join(partes)


def _uso_gemini(bruto: Any) -> Uso | None:
    if bruto is None:
        return None
    return Uso(
        prompt_tokens=getattr(bruto, "total_input_tokens", None),
        completion_tokens=getattr(bruto, "total_output_tokens", None),
        total_tokens=getattr(bruto, "total_tokens", None),
    )


def _traduzir_erro_gemini(erro: Exception) -> ErroDoProvedor:
    codigo = getattr(erro, "code", None)
    mensagem = getattr(erro, "message", None) or str(erro)
    retentavel = codigo == 429 or (isinstance(codigo, int) and codigo >= 500)
    return ErroDoProvedor(
        f"Gemini respondeu {codigo}: {mensagem}",
        status=codigo if isinstance(codigo, int) else None,
        retentavel=retentavel,
        codigo="gemini",
    )


def _descrever(erro: Any) -> str:
    mensagem = getattr(erro, "message", None)
    return str(mensagem if mensagem is not None else erro)


def _texto_da_resposta(bruto: Mapping) -> str:
    escolhas = bruto.get("choices") or []
    if not escolhas or not isinstance(escolhas[0], Mapping):
        return ""
    mensagem = escolhas[0].get("message") or {}
    if not isinstance(mensagem, Mapping):
        return ""
    conteudo = mensagem.get("content")
    if isinstance(conteudo, str):
        return conteudo
    if isinstance(conteudo, list):
        return "".join(
            parte.get("text", "")
            for parte in conteudo
            if isinstance(parte, Mapping)
        )
    return ""


def _uso_de(bruto: Mapping) -> Uso:
    return Uso(
        prompt_tokens=bruto.get("prompt_tokens"),
        completion_tokens=bruto.get("completion_tokens"),
        total_tokens=bruto.get("total_tokens"),
    )


def _mensagem_de_erro(erro: object) -> str:
    if isinstance(erro, Mapping):
        return str(erro.get("message") or erro)
    return str(erro)
