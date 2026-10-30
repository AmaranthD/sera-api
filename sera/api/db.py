from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Sequence
from uuid import uuid4

from anyio import to_thread

from .. import rag

VERSAO_SCHEMA = 2

_CORTE_RELATIVO = 0.65

_SQL_V1 = """
CREATE TABLE IF NOT EXISTS pessoas (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    faixa_etaria TEXT NOT NULL
        CHECK (faixa_etaria IN ('adulto', 'adolescente', 'crianca')),
    perfil TEXT NOT NULL
        CHECK (perfil IN ('padrao', 'crianca_adolescente', 'idoso_ou_pouco_tecnico')),
    criada_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversas (
    id TEXT PRIMARY KEY,
    pessoa_id TEXT NOT NULL REFERENCES pessoas(id) ON DELETE CASCADE,
    titulo TEXT,
    criada_em TEXT NOT NULL,
    atualizada_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conversas_pessoa
    ON conversas(pessoa_id, atualizada_em DESC);

CREATE TABLE IF NOT EXISTS mensagens (
    id TEXT PRIMARY KEY,
    conversa_id TEXT NOT NULL REFERENCES conversas(id) ON DELETE CASCADE,
    papel TEXT NOT NULL CHECK (papel IN ('user', 'assistant')),
    conteudo TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('completa', 'interrompida', 'erro')),
    criada_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mensagens_conversa
    ON mensagens(conversa_id, criada_em);

CREATE TABLE IF NOT EXISTS memorias (
    id TEXT PRIMARY KEY,
    pessoa_id TEXT NOT NULL REFERENCES pessoas(id) ON DELETE CASCADE,
    texto TEXT NOT NULL,
    categoria TEXT NOT NULL
        CHECK (categoria IN ('familia', 'trabalho', 'gostos', 'rotina', 'saude', 'outro')),
    criada_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memorias_pessoa ON memorias(pessoa_id);

CREATE TABLE IF NOT EXISTS nao_mencionar (
    pessoa_id TEXT NOT NULL REFERENCES pessoas(id) ON DELETE CASCADE,
    tema TEXT NOT NULL,
    PRIMARY KEY (pessoa_id, tema)
);

CREATE TABLE IF NOT EXISTS ajustes (
    id TEXT PRIMARY KEY,
    pessoa_id TEXT NOT NULL REFERENCES pessoas(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL CHECK (tipo IN (
        'apelido', 'piada_interna', 'formato', 'assunto',
        'nivel_sarcasmo', 'formalidade', 'nivel_tecnico', 'toque_yandere'
    )),
    texto TEXT,
    valor TEXT,
    origem TEXT NOT NULL CHECK (origem IN ('conversa', 'manual')),
    criada_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ajustes_pessoa ON ajustes(pessoa_id);
"""


_SQL_V2 = """
ALTER TABLE pessoas ADD COLUMN acesso_vault INTEGER NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS notas (
    caminho TEXT PRIMARY KEY,
    titulo TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    hash TEXT NOT NULL,
    atualizada_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trechos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    caminho TEXT NOT NULL REFERENCES notas(caminho) ON DELETE CASCADE,
    ordem INTEGER NOT NULL,
    secao TEXT NOT NULL,
    texto TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trechos_caminho ON trechos(caminho, ordem);

CREATE VIRTUAL TABLE IF NOT EXISTS trechos_fts USING fts5(
    secao, texto, titulo, tags,
    tokenize = "unicode61 remove_diacritics 2"
);
"""


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Banco:
    def __init__(self, caminho: str | Path) -> None:
        self.caminho = Path(caminho)

    def iniciar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self._conexao() as conn:
            versao = conn.execute("PRAGMA user_version").fetchone()[0]
            if versao > VERSAO_SCHEMA:
                raise RuntimeError(
                    f"banco na versão {versao}, mas o código suporta até "
                    f"{VERSAO_SCHEMA}"
                )
            if versao < 1:
                conn.executescript(_SQL_V1)
                conn.execute("PRAGMA user_version = 1")
            if versao < 2:
                conn.executescript(_SQL_V2)
                conn.execute("PRAGMA user_version = 2")

    @contextmanager
    def _conexao(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.caminho)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def criar_pessoa(
        self,
        pessoa_id: str,
        nome: str,
        faixa_etaria: str,
        perfil: str,
        acesso_vault: bool = True,
    ) -> dict:
        return await to_thread.run_sync(
            self._criar_pessoa,
            pessoa_id,
            nome,
            faixa_etaria,
            perfil,
            acesso_vault,
        )

    async def indexar_notas(self, notas: Sequence[Nota]) -> dict:
        return await to_thread.run_sync(self._indexar_notas, list(notas))

    async def buscar_trechos(self, consulta: str, limite: int) -> list[dict]:
        return await to_thread.run_sync(
            self._buscar_trechos, consulta, limite
        )

    async def estatisticas_indice(self) -> dict:
        return await to_thread.run_sync(self._estatisticas_indice)

    async def limpar_indice(self) -> None:
        await to_thread.run_sync(self._limpar_indice)

    async def obter_pessoa(self, pessoa_id: str) -> dict | None:
        return await to_thread.run_sync(self._obter_pessoa, pessoa_id)

    async def listar_pessoas(self) -> list[dict]:
        return await to_thread.run_sync(self._listar_pessoas)

    async def apagar_pessoa(self, pessoa_id: str) -> bool:
        return await to_thread.run_sync(self._apagar_pessoa, pessoa_id)

    async def criar_conversa(
        self, pessoa_id: str, titulo: str | None = None
    ) -> dict:
        return await to_thread.run_sync(
            self._criar_conversa, pessoa_id, titulo
        )

    async def obter_conversa(self, conversa_id: str) -> dict | None:
        return await to_thread.run_sync(self._obter_conversa, conversa_id)

    async def listar_conversas(self, pessoa_id: str) -> list[dict]:
        return await to_thread.run_sync(self._listar_conversas, pessoa_id)

    async def criar_mensagem(
        self,
        conversa_id: str,
        papel: str,
        conteudo: str,
        status: str = "completa",
    ) -> dict:
        return await to_thread.run_sync(
            self._criar_mensagem, conversa_id, papel, conteudo, status
        )

    async def ultimas_mensagens(
        self, conversa_id: str, limite: int
    ) -> list[dict]:
        return await to_thread.run_sync(
            self._ultimas_mensagens, conversa_id, limite
        )

    async def listar_mensagens(self, conversa_id: str) -> list[dict]:
        return await to_thread.run_sync(self._listar_mensagens, conversa_id)

    async def criar_memoria(
        self, pessoa_id: str, texto: str, categoria: str
    ) -> dict:
        return await to_thread.run_sync(
            self._criar_memoria, pessoa_id, texto, categoria
        )

    async def listar_memorias(self, pessoa_id: str) -> list[dict]:
        return await to_thread.run_sync(self._listar_memorias, pessoa_id)

    async def apagar_memoria(self, pessoa_id: str, memoria_id: str) -> bool:
        return await to_thread.run_sync(
            self._apagar_memoria, pessoa_id, memoria_id
        )

    async def adicionar_tema(self, pessoa_id: str, tema: str) -> bool:
        return await to_thread.run_sync(
            self._adicionar_tema, pessoa_id, tema
        )

    async def listar_temas(self, pessoa_id: str) -> list[str]:
        return await to_thread.run_sync(self._listar_temas, pessoa_id)

    async def remover_tema(self, pessoa_id: str, tema: str) -> bool:
        return await to_thread.run_sync(self._remover_tema, pessoa_id, tema)

    async def criar_ajuste(
        self,
        pessoa_id: str,
        tipo: str,
        texto: str | None,
        valor: str | None,
        origem: str,
    ) -> dict:
        return await to_thread.run_sync(
            self._criar_ajuste, pessoa_id, tipo, texto, valor, origem
        )

    async def listar_ajustes(self, pessoa_id: str) -> list[dict]:
        return await to_thread.run_sync(self._listar_ajustes, pessoa_id)

    async def apagar_ajuste(self, pessoa_id: str, ajuste_id: str) -> bool:
        return await to_thread.run_sync(
            self._apagar_ajuste, pessoa_id, ajuste_id
        )

    def _criar_pessoa(
        self,
        pessoa_id: str,
        nome: str,
        faixa_etaria: str,
        perfil: str,
        acesso_vault: bool = True,
    ) -> dict:
        momento = agora()
        with self._conexao() as conn:
            conn.execute(
                "INSERT INTO pessoas "
                "(id, nome, faixa_etaria, perfil, criada_em, acesso_vault) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    pessoa_id,
                    nome,
                    faixa_etaria,
                    perfil,
                    momento,
                    int(bool(acesso_vault)),
                ),
            )
            return dict(
                conn.execute(
                    "SELECT * FROM pessoas WHERE id = ?", (pessoa_id,)
                ).fetchone()
            )

    def _obter_pessoa(self, pessoa_id: str) -> dict | None:
        with self._conexao() as conn:
            linha = conn.execute(
                "SELECT * FROM pessoas WHERE id = ?", (pessoa_id,)
            ).fetchone()
            return dict(linha) if linha else None

    def _listar_pessoas(self) -> list[dict]:
        with self._conexao() as conn:
            return [
                dict(linha)
                for linha in conn.execute(
                    "SELECT * FROM pessoas ORDER BY nome COLLATE NOCASE"
                )
            ]

    def _apagar_pessoa(self, pessoa_id: str) -> bool:
        with self._conexao() as conn:
            cursor = conn.execute("DELETE FROM pessoas WHERE id = ?", (pessoa_id,))
            return cursor.rowcount > 0

    def _criar_conversa(
        self, pessoa_id: str, titulo: str | None = None
    ) -> dict:
        conversa_id = _novo_id()
        momento = agora()
        with self._conexao() as conn:
            conn.execute(
                "INSERT INTO conversas "
                "(id, pessoa_id, titulo, criada_em, atualizada_em) "
                "VALUES (?, ?, ?, ?, ?)",
                (conversa_id, pessoa_id, titulo, momento, momento),
            )
            return dict(
                conn.execute(
                    "SELECT * FROM conversas WHERE id = ?", (conversa_id,)
                ).fetchone()
            )

    def _obter_conversa(self, conversa_id: str) -> dict | None:
        with self._conexao() as conn:
            linha = conn.execute(
                "SELECT * FROM conversas WHERE id = ?", (conversa_id,)
            ).fetchone()
            return dict(linha) if linha else None

    def _listar_conversas(self, pessoa_id: str) -> list[dict]:
        with self._conexao() as conn:
            return [
                dict(linha)
                for linha in conn.execute(
                    "SELECT * FROM conversas WHERE pessoa_id = ? "
                    "ORDER BY atualizada_em DESC, rowid DESC",
                    (pessoa_id,),
                )
            ]

    def _criar_mensagem(
        self, conversa_id: str, papel: str, conteudo: str, status: str
    ) -> dict:
        mensagem_id = _novo_id()
        momento = agora()
        with self._conexao() as conn:
            conn.execute(
                "INSERT INTO mensagens "
                "(id, conversa_id, papel, conteudo, status, criada_em) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (mensagem_id, conversa_id, papel, conteudo, status, momento),
            )
            conn.execute(
                "UPDATE conversas SET atualizada_em = ? WHERE id = ?",
                (momento, conversa_id),
            )
            return dict(
                conn.execute(
                    "SELECT * FROM mensagens WHERE id = ?", (mensagem_id,)
                ).fetchone()
            )

    def _ultimas_mensagens(self, conversa_id: str, limite: int) -> list[dict]:
        with self._conexao() as conn:
            return [
                dict(linha)
                for linha in conn.execute(
                    "SELECT id, papel, conteudo, status, criada_em FROM ("
                    "  SELECT rowid AS seq, id, papel, conteudo, status, criada_em"
                    "  FROM mensagens"
                    "  WHERE conversa_id = ? AND status = 'completa'"
                    "  ORDER BY rowid DESC LIMIT ?"
                    ") ORDER BY seq ASC",
                    (conversa_id, limite),
                )
            ]

    def _listar_mensagens(self, conversa_id: str) -> list[dict]:
        with self._conexao() as conn:
            return [
                dict(linha)
                for linha in conn.execute(
                    "SELECT id, papel, conteudo, status, criada_em "
                    "FROM mensagens WHERE conversa_id = ? ORDER BY rowid ASC",
                    (conversa_id,),
                )
            ]

    def _criar_memoria(
        self, pessoa_id: str, texto: str, categoria: str
    ) -> dict:
        memoria_id = _novo_id()
        momento = agora()
        with self._conexao() as conn:
            conn.execute(
                "INSERT INTO memorias "
                "(id, pessoa_id, texto, categoria, criada_em) "
                "VALUES (?, ?, ?, ?, ?)",
                (memoria_id, pessoa_id, texto, categoria, momento),
            )
            return dict(
                conn.execute(
                    "SELECT * FROM memorias WHERE id = ?", (memoria_id,)
                ).fetchone()
            )

    def _listar_memorias(self, pessoa_id: str) -> list[dict]:
        with self._conexao() as conn:
            return [
                dict(linha)
                for linha in conn.execute(
                    "SELECT * FROM memorias WHERE pessoa_id = ? "
                    "ORDER BY criada_em ASC, rowid ASC",
                    (pessoa_id,),
                )
            ]

    def _apagar_memoria(self, pessoa_id: str, memoria_id: str) -> bool:
        with self._conexao() as conn:
            cursor = conn.execute(
                "DELETE FROM memorias WHERE id = ? AND pessoa_id = ?",
                (memoria_id, pessoa_id),
            )
            return cursor.rowcount > 0

    def _adicionar_tema(self, pessoa_id: str, tema: str) -> bool:
        with self._conexao() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO nao_mencionar (pessoa_id, tema) VALUES (?, ?)",
                (pessoa_id, tema),
            )
            return cursor.rowcount > 0

    def _listar_temas(self, pessoa_id: str) -> list[str]:
        with self._conexao() as conn:
            return [
                linha["tema"]
                for linha in conn.execute(
                    "SELECT tema FROM nao_mencionar WHERE pessoa_id = ? "
                    "ORDER BY tema",
                    (pessoa_id,),
                )
            ]

    def _remover_tema(self, pessoa_id: str, tema: str) -> bool:
        with self._conexao() as conn:
            cursor = conn.execute(
                "DELETE FROM nao_mencionar WHERE pessoa_id = ? AND tema = ?",
                (pessoa_id, tema),
            )
            return cursor.rowcount > 0

    def _criar_ajuste(
        self,
        pessoa_id: str,
        tipo: str,
        texto: str | None,
        valor: str | None,
        origem: str,
    ) -> dict:
        ajuste_id = _novo_id()
        momento = agora()
        with self._conexao() as conn:
            conn.execute(
                "INSERT INTO ajustes "
                "(id, pessoa_id, tipo, texto, valor, origem, criada_em) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ajuste_id, pessoa_id, tipo, texto, valor, origem, momento),
            )
            return dict(
                conn.execute(
                    "SELECT * FROM ajustes WHERE id = ?", (ajuste_id,)
                ).fetchone()
            )

    def _listar_ajustes(self, pessoa_id: str) -> list[dict]:
        with self._conexao() as conn:
            return [
                dict(linha)
                for linha in conn.execute(
                    "SELECT * FROM ajustes WHERE pessoa_id = ? "
                    "ORDER BY criada_em ASC, rowid ASC",
                    (pessoa_id,),
                )
            ]

    def _apagar_ajuste(self, pessoa_id: str, ajuste_id: str) -> bool:
        with self._conexao() as conn:
            cursor = conn.execute(
                "DELETE FROM ajustes WHERE id = ? AND pessoa_id = ?",
                (ajuste_id, pessoa_id),
            )
            return cursor.rowcount > 0


    def _indexar_notas(self, notas: Sequence[Nota]) -> dict:
        novas = atualizadas = removidas = trechos = 0
        momento = agora()
        with self._conexao() as conn:
            existentes = {
                linha["caminho"]: linha["hash"]
                for linha in conn.execute("SELECT caminho, hash FROM notas")
            }
            vistos: set[str] = set()
            for nota in notas:
                vistos.add(nota.caminho)
                if existentes.get(nota.caminho) == nota.hash:
                    continue
                if nota.caminho in existentes:
                    atualizadas += 1
                else:
                    novas += 1
                self._apagar_nota(conn, nota.caminho)
                conn.execute(
                    "INSERT INTO notas (caminho, titulo, tags, hash, atualizada_em) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        nota.caminho,
                        nota.titulo,
                        " ".join(nota.tags),
                        nota.hash,
                        momento,
                    ),
                )
                for secao in nota.secoes:
                    cursor = conn.execute(
                        "INSERT INTO trechos (caminho, ordem, secao, texto) "
                        "VALUES (?, ?, ?, ?)",
                        (nota.caminho, secao.ordem, secao.nome, secao.texto),
                    )
                    conn.execute(
                        "INSERT INTO trechos_fts (rowid, secao, texto, titulo, tags) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            cursor.lastrowid,
                            secao.nome,
                            secao.texto,
                            nota.titulo,
                            " ".join(nota.tags),
                        ),
                    )
                    trechos += 1

            for caminho in existentes.keys() - vistos:
                self._apagar_nota(conn, caminho)
                removidas += 1

        return {
            "notas_novas": novas,
            "notas_atualizadas": atualizadas,
            "notas_removidas": removidas,
            "trechos_indexados": trechos,
        }

    def _apagar_nota(self, conn: sqlite3.Connection, caminho: str) -> None:
        conn.execute(
            "DELETE FROM trechos_fts WHERE rowid IN "
            "(SELECT id FROM trechos WHERE caminho = ?)",
            (caminho,),
        )
        conn.execute("DELETE FROM trechos WHERE caminho = ?", (caminho,))
        conn.execute("DELETE FROM notas WHERE caminho = ?", (caminho,))

    def _buscar_trechos(self, consulta: str, limite: int) -> list[dict]:
        termos = rag.termos_busca(consulta)
        if not termos or limite <= 0:
            return []

        with self._conexao() as conn:
            total = conn.execute("SELECT COUNT(*) FROM notas").fetchone()[0]
            if not total:
                return []
            expressao = rag.expressao_fts(consulta)
            try:
                ranqueadas = conn.execute(
                    "SELECT trechos.caminho, notas.titulo, "
                    "bm25(trechos_fts, 3.0, 1.0, 6.0, 4.0) AS score "
                    "FROM trechos_fts "
                    "JOIN trechos ON trechos.id = trechos_fts.rowid "
                    "JOIN notas ON notas.caminho = trechos.caminho "
                    "WHERE trechos_fts MATCH ? "
                    "ORDER BY score",
                    (expressao,),
                ).fetchall()
            except sqlite3.OperationalError:
                return []

            escolhidas: list[tuple[str, str]] = []
            vistos: set[str] = set()
            melhor = ranqueadas[0]["score"] if ranqueadas else 0.0
            corte = melhor * _CORTE_RELATIVO
            for linha in ranqueadas:
                if melhor < 0 and linha["score"] > corte:
                    break
                if linha["caminho"] in vistos:
                    continue
                vistos.add(linha["caminho"])
                escolhidas.append((linha["caminho"], linha["titulo"]))
                if len(escolhidas) >= limite:
                    break

            trechos: list[dict] = []
            for caminho, titulo in escolhidas:
                for linha in conn.execute(
                    "SELECT secao, texto FROM trechos "
                    "WHERE caminho = ? ORDER BY ordem",
                    (caminho,),
                ):
                    trechos.append(
                        {
                            "nota": titulo,
                            "secao": linha["secao"],
                            "texto": linha["texto"],
                        }
                    )
            return trechos

    def _estatisticas_indice(self) -> dict:
        with self._conexao() as conn:
            return {
                "notas": conn.execute("SELECT COUNT(*) FROM notas").fetchone()[0],
                "trechos": conn.execute(
                    "SELECT COUNT(*) FROM trechos"
                ).fetchone()[0],
            }

    def _limpar_indice(self) -> None:
        with self._conexao() as conn:
            conn.execute("DELETE FROM trechos_fts")
            conn.execute("DELETE FROM trechos")
            conn.execute("DELETE FROM notas")


def _novo_id() -> str:
    return uuid4().hex
