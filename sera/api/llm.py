from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator, Mapping, Protocol, Sequence

import anyio
import httpx

from .config import Config
from .root import DIAGNOSTICO

logger = logging.getLogger(__name__)

try:
    from google.genai import errors as _gemini_errors
except ImportError:
    _gemini_errors = None


@dataclass(frozen=True)
class Delta:
    texto: str


@dataclass(frozen=True)
class ChamadaFerramenta:
    id: str
    nome: str
    argumentos: str


@dataclass(frozen=True)
class Ferramenta:
    chamadas: tuple[ChamadaFerramenta, ...]


@dataclass(frozen=True)
class Uso:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class Fim:
    uso: Uso | None = None
    modelo: str | None = None


Evento = Delta | Ferramenta | Fim


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
        mensagens: Sequence[Mapping[str, Any]],
        *,
        temperatura: float,
        max_tokens: int,
        ferramentas: Sequence[Mapping[str, Any]] | None = None,
        escolha_ferramenta: str | None = None,
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
        mensagens: Sequence[Mapping[str, Any]],
        *,
        temperatura: float,
        max_tokens: int,
        ferramentas: Sequence[Mapping[str, Any]] | None = None,
        escolha_ferramenta: str | None = None,
    ) -> AsyncIterator[Evento]:
        tentativas = 0
        while True:
            emitido = False
            try:
                async for evento in self._tentativa(
                    mensagens, temperatura, max_tokens
                ):
                    if isinstance(evento, (Delta, Ferramenta)):
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

        yield Fim(uso, self._config.llm_model)


class ClienteOpenAICompat:
    def __init__(
        self,
        config: Config,
        *,
        transporte: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config
        self._transporte = transporte
        self._cliente: httpx.AsyncClient | None = None

    def _obter_cliente(self) -> httpx.AsyncClient:
        if self._cliente is None:
            self._cliente = httpx.AsyncClient(transport=self._transporte)
        return self._cliente

    async def fechar(self) -> None:
        if self._cliente is not None:
            await self._cliente.aclose()
            self._cliente = None

    async def stream(
        self,
        mensagens: Sequence[Mapping[str, Any]],
        *,
        temperatura: float,
        max_tokens: int,
        ferramentas: Sequence[Mapping[str, Any]] | None = None,
        escolha_ferramenta: str | None = None,
    ) -> AsyncIterator[Evento]:
        incluir_uso = True
        usar_ferramentas = bool(ferramentas)
        tentativas = 0
        while True:
            emitido = False
            try:
                async for evento in self._tentativa(
                    mensagens,
                    temperatura,
                    max_tokens,
                    incluir_uso,
                    ferramentas if usar_ferramentas else None,
                    escolha_ferramenta,
                ):
                    if isinstance(evento, (Delta, Ferramenta)):
                        emitido = True
                    yield evento
                return
            except ErroDoProvedor as erro:
                if erro.codigo == "stream_options" and incluir_uso:
                    incluir_uso = False
                    continue
                if erro.codigo == "ferramentas" and usar_ferramentas:
                    usar_ferramentas = False
                    continue
                if emitido or not erro.retentavel or tentativas >= 1:
                    raise
                tentativas += 1
                await anyio.sleep(0.5)

    async def _tentativa(
        self,
        mensagens: Sequence[Mapping[str, Any]],
        temperatura: float,
        max_tokens: int,
        incluir_uso: bool,
        ferramentas: Sequence[Mapping[str, Any]] | None,
        escolha_ferramenta: str | None = None,
    ) -> AsyncIterator[Evento]:
        config = self._config
        payload: dict = {
            "model": config.llm_model,
            "messages": [_mensagem_para_payload(mensagem) for mensagem in mensagens],
            "stream": True,
            "temperature": temperatura,
            "max_tokens": max_tokens,
        }
        if incluir_uso:
            payload["stream_options"] = {"include_usage": True}
        if ferramentas:
            payload["tools"] = [dict(ferramenta) for ferramenta in ferramentas]
            if escolha_ferramenta:
                payload["tool_choice"] = escolha_ferramenta

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
            cliente = self._obter_cliente()
            async with cliente.stream(
                "POST", url, json=payload, headers=cabecalhos, timeout=timeout
            ) as resposta:
                if resposta.status_code >= 400:
                    corpo = (await resposta.aread()).decode("utf-8", "replace")
                    codigo = "http"
                    if resposta.status_code == 400:
                        if "stream_options" in corpo:
                            codigo = "stream_options"
                        elif ferramentas and "tool" in corpo.lower():
                            codigo = "ferramentas"
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
                    chamadas = _chamadas_da_resposta(bruto)
                    if chamadas:
                        yield Ferramenta(tuple(chamadas))
                    bruto_uso = bruto.get("usage")
                    yield Fim(
                        _uso_de(bruto_uso) if bruto_uso else None,
                        self._config.llm_model,
                    )
                    return

                acumuladas: dict[int, dict] = {}
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
                        for bruto_chamada in delta.get("tool_calls") or []:
                            _acumular_chamada(acumuladas, bruto_chamada)
        except httpx.TimeoutException as erro:
            raise ErroDoProvedor(
                f"timeout ao falar com o provedor: {erro}",
                codigo="timeout",
                retentavel=False,
            ) from erro
        except httpx.RequestError as erro:
            raise ErroDoProvedor(
                f"falha de rede ao falar com o provedor: {erro}",
                codigo="rede",
                retentavel=True,
            ) from erro

        chamadas = _chamadas_acumuladas(acumuladas)
        if chamadas:
            yield Ferramenta(tuple(chamadas))
        yield Fim(uso, self._config.llm_model)


class ClienteComFallback:
    """Usa o provedor principal e cai para a reserva quando ele falha.

    A troca só acontece antes do primeiro token/ferramenta: depois disso a
    resposta já começou a chegar ao cliente e repetir o texto duplicaria a
    saída.
    """

    def __init__(self, primario: ClienteLLM, reserva: ClienteLLM) -> None:
        self._primario = primario
        self._reserva = reserva

    async def stream(
        self,
        mensagens: Sequence[Mapping[str, Any]],
        *,
        temperatura: float,
        max_tokens: int,
        ferramentas: Sequence[Mapping[str, Any]] | None = None,
        escolha_ferramenta: str | None = None,
    ) -> AsyncIterator[Evento]:
        emitido = False
        try:
            async for evento in self._primario.stream(
                mensagens,
                temperatura=temperatura,
                max_tokens=max_tokens,
                ferramentas=ferramentas,
                escolha_ferramenta=escolha_ferramenta,
            ):
                emitido = True
                yield evento
            return
        except ErroDoProvedor as erro:
            if emitido:
                raise
            DIAGNOSTICO.erro("llm_principal", str(erro))
            logger.warning(
                "provedor principal falhou antes do primeiro token (%s); "
                "usando fallback",
                erro,
            )
        DIAGNOSTICO.fallback()
        async for evento in self._reserva.stream(
            mensagens,
            temperatura=temperatura,
            max_tokens=max_tokens,
            ferramentas=ferramentas,
            escolha_ferramenta=escolha_ferramenta,
        ):
            yield evento

    async def fechar(self) -> None:
        for cliente in (self._primario, self._reserva):
            fechar = getattr(cliente, "fechar", None)
            if fechar is not None:
                await fechar()


def _mensagem_para_payload(mensagem: Mapping[str, Any]) -> dict:
    return dict(mensagem)


def _acumular_chamada(acumuladas: dict[int, dict], bruto: Any) -> None:
    if not isinstance(bruto, Mapping):
        return
    indice = bruto.get("index")
    if not isinstance(indice, int):
        indice = max(acumuladas, default=0) if acumuladas else 0
    atual = acumuladas.setdefault(
        indice, {"id": "", "nome": "", "argumentos": ""}
    )
    if bruto.get("id"):
        atual["id"] = str(bruto["id"])
    funcao = bruto.get("function")
    if isinstance(funcao, Mapping):
        if funcao.get("name"):
            atual["nome"] = str(funcao["name"])
        argumentos = funcao.get("arguments")
        if argumentos:
            atual["argumentos"] += str(argumentos)


def _chamadas_acumuladas(
    acumuladas: Mapping[int, Mapping[str, str]],
) -> list[ChamadaFerramenta]:
    chamadas: list[ChamadaFerramenta] = []
    for indice in sorted(acumuladas):
        dados = acumuladas[indice]
        nome = str(dados.get("nome") or "")
        if not nome:
            continue
        chamadas.append(
            ChamadaFerramenta(
                id=str(dados.get("id") or f"call_{indice}"),
                nome=nome,
                argumentos=str(dados.get("argumentos") or "{}"),
            )
        )
    return chamadas


def _chamadas_da_resposta(bruto: Mapping) -> list[ChamadaFerramenta]:
    escolhas = bruto.get("choices") or []
    if not escolhas or not isinstance(escolhas[0], Mapping):
        return []
    mensagem = escolhas[0].get("message") or {}
    if not isinstance(mensagem, Mapping):
        return []
    chamadas: list[ChamadaFerramenta] = []
    for indice, bruta in enumerate(mensagem.get("tool_calls") or []):
        if not isinstance(bruta, Mapping):
            continue
        funcao = bruta.get("function") or {}
        if not isinstance(funcao, Mapping):
            continue
        nome = str(funcao.get("name") or "")
        if not nome:
            continue
        chamadas.append(
            ChamadaFerramenta(
                id=str(bruta.get("id") or f"call_{indice}"),
                nome=nome,
                argumentos=str(funcao.get("arguments") or "{}"),
            )
        )
    return chamadas


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
