from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)


class GerenciadorJobs:
    """Tarefas de geração que continuam vivas depois do request.

    O request só cria a mensagem `gerando` e agenda a corotina; quem
    acompanha o andamento é o polling em `/conversas/{id}/mensagens`.
    """

    def __init__(self) -> None:
        self._tarefas: dict[str, asyncio.Task[None]] = {}
        self._tranca = asyncio.Lock()

    def trancar(self) -> asyncio.Lock:
        """Serializa a checagem/criação de um job por conversa."""
        return self._tranca

    def ativa(self, resposta_id: str) -> bool:
        tarefa = self._tarefas.get(resposta_id)
        return tarefa is not None and not tarefa.done()

    def iniciar(
        self,
        resposta_id: str,
        corotina: Coroutine[Any, Any, None],
    ) -> asyncio.Task[None]:
        tarefa = asyncio.create_task(corotina)
        self._tarefas[resposta_id] = tarefa
        tarefa.add_done_callback(
            lambda concluida: self._esquecer(resposta_id, concluida)
        )
        return tarefa

    def cancelar(self, resposta_id: str) -> bool:
        tarefa = self._tarefas.get(resposta_id)
        if tarefa is None or tarefa.done():
            return False
        tarefa.cancel()
        return True

    async def encerrar(self, limite: float = 10.0) -> None:
        """Cancela tudo no shutdown; cada job marca a própria mensagem."""
        tarefas = list(self._tarefas.values())
        for tarefa in tarefas:
            tarefa.cancel()
        try:
            if tarefas:
                await asyncio.wait_for(
                    asyncio.gather(*tarefas, return_exceptions=True),
                    limite,
                )
        except asyncio.TimeoutError:
            logger.warning(
                "shutdown: %s jobs não terminaram em %.1fs",
                len(tarefas),
                limite,
            )
        finally:
            self._tarefas.clear()

    def _esquecer(
        self, resposta_id: str, tarefa: asyncio.Task[None]
    ) -> None:
        if self._tarefas.get(resposta_id) is tarefa:
            self._tarefas.pop(resposta_id, None)
        if not tarefa.cancelled() and tarefa.exception() is not None:
            logger.warning(
                "job %s terminou com erro: %s",
                resposta_id,
                tarefa.exception(),
            )
