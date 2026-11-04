from __future__ import annotations

from typing import Mapping, Sequence

from .ferramentas_agenda import (
    ESQUEMA_AGENDAR,
    ESQUEMA_CANCELAR_COMPROMISSO,
    ESQUEMA_CONSULTAR_AGENDA,
    INSTRUCAO_AGENDA,
    _agendar,
    _cancelar_compromisso,
    _consultar_agenda,
)
from .ferramentas_base import (
    ContextoFerramentas,
    FerramentaDesconhecida,
    FerramentaInvalida,
    NOME_AGENDAR,
    NOME_AJUSTAR,
    NOME_CANCELAR_COMPROMISSO,
    NOME_CONSULTAR_AGENDA,
    NOME_ESQUECER,
    NOME_JW,
    NOME_LEMBRAR,
    NOME_PESQUISA,
    NOME_TEXTO_DIARIO,
    _ler_argumentos,
)
from .ferramentas_busca import (
    ESQUEMA_PESQUISAR_WEB,
    INSTRUCAO_BUSCA,
    bloco_resultados,
    consulta_explicita,
)
from .ferramentas_jw import (
    ESQUEMA_JW,
    INSTRUCAO_JW,
    INSTRUCAO_JW_MODO,
    _esquema_jw,
    _jw,
    extrair_urls_jw,
    ferramentas_jw_para,
    fontes_jw,
    formatar_resultado_jw,
    referencia_biblica,
    titulo_fonte_jw,
)
from .ferramentas_memoria import (
    ESQUEMA_AJUSTAR,
    ESQUEMA_ESQUECER,
    ESQUEMA_LEMBRAR,
    INSTRUCAO_MEMORIA,
    _ajustar,
    _esquecer,
    _lembrar,
    consulta_esquecimento,
)
from .ferramentas_texto_diario import (
    ESQUEMA_TEXTO_DIARIO,
    INSTRUCAO_TEXTO_DIARIO,
    _texto_diario,
)

__all__ = [
    "ContextoFerramentas",
    "FerramentaDesconhecida",
    "FerramentaInvalida",
    "NOME_AGENDAR",
    "NOME_AJUSTAR",
    "NOME_CANCELAR_COMPROMISSO",
    "NOME_CONSULTAR_AGENDA",
    "NOME_ESQUECER",
    "NOME_JW",
    "NOME_LEMBRAR",
    "NOME_PESQUISA",
    "NOME_TEXTO_DIARIO",
    "INSTRUCAO_AGENDA",
    "INSTRUCAO_BUSCA",
    "INSTRUCAO_JW",
    "INSTRUCAO_JW_MODO",
    "INSTRUCAO_MEMORIA",
    "INSTRUCAO_TEXTO_DIARIO",
    "ESQUEMA_JW",
    "bloco_resultados",
    "consulta_esquecimento",
    "consulta_explicita",
    "esquemas",
    "executar_ferramenta",
    "extrair_urls_jw",
    "ferramentas_jw_para",
    "fontes_jw",
    "formatar_resultado_jw",
    "referencia_biblica",
    "titulo_fonte_jw",
]


def esquemas(
    *,
    busca: bool = False,
    aprendizado: bool = False,
    agenda: bool = False,
    jw: bool = False,
    jw_ferramentas: Sequence[str] | None = None,
    texto_diario: bool = False,
) -> list[dict]:
    lista: list[dict] = []
    if busca:
        lista.append(ESQUEMA_PESQUISAR_WEB)
    if jw:
        lista.append(_esquema_jw(jw_ferramentas))
    if agenda:
        lista.extend(
            (
                ESQUEMA_AGENDAR,
                ESQUEMA_CONSULTAR_AGENDA,
                ESQUEMA_CANCELAR_COMPROMISSO,
            )
        )
    if texto_diario:
        lista.append(ESQUEMA_TEXTO_DIARIO)
    if aprendizado:
        lista.extend((ESQUEMA_LEMBRAR, ESQUEMA_AJUSTAR, ESQUEMA_ESQUECER))
    return lista


async def executar_ferramenta(
    nome: str,
    argumentos: str | Mapping | None,
    contexto: ContextoFerramentas,
) -> dict:
    dados = _ler_argumentos(argumentos)

    if nome == NOME_PESQUISA:
        if contexto.busca is None:
            raise FerramentaInvalida("a busca na internet está desligada")
        consulta = " ".join(str(dados.get("consulta") or "").split())
        if len(consulta) < 2:
            raise FerramentaInvalida("a consulta está vazia")
        resultados = await contexto.busca.pesquisar(consulta)
        return {
            "consulta": consulta,
            "resultados": [resultado.como_dict() for resultado in resultados],
        }

    if nome == NOME_JW:
        return await _jw(dados, contexto)

    if nome == NOME_AGENDAR:
        return await _agendar(dados, contexto)

    if nome == NOME_CONSULTAR_AGENDA:
        return await _consultar_agenda(dados, contexto)

    if nome == NOME_CANCELAR_COMPROMISSO:
        return await _cancelar_compromisso(dados, contexto)

    if nome == NOME_TEXTO_DIARIO:
        return await _texto_diario(dados, contexto)

    if nome == NOME_LEMBRAR:
        return await _lembrar(dados, contexto)

    if nome == NOME_AJUSTAR:
        return await _ajustar(dados, contexto)

    if nome == NOME_ESQUECER:
        return await _esquecer(dados, contexto)

    raise FerramentaDesconhecida(nome)
