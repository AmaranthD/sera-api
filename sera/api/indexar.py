from __future__ import annotations

import argparse
from pathlib import Path

import anyio

from ..rag import iterar_notas
from .config import Config
from .db import Banco


async def _indexar(args: argparse.Namespace, banco: Banco) -> int:
    if args.limpar:
        await banco.limpar_indice()

    notas = list(iterar_notas(args.notas))
    resultado = await banco.indexar_notas(notas)
    total = await banco.estatisticas_indice()

    print(f"notas lidas: {len(notas)}")
    print(
        "novas: {notas_novas} | atualizadas: {notas_atualizadas} | "
        "removidas: {notas_removidas} | trechos: {trechos_indexados}".format(
            **resultado
        )
    )
    print(f"índice: {total['notas']} nota(s), {total['trechos']} trecho(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    config = Config.de_env()
    parser = argparse.ArgumentParser(
        prog="sera.indexar",
        description="Indexa as notas Markdown no SQLite da Sera (FTS5).",
    )
    parser.add_argument(
        "--notas",
        type=Path,
        default=config.notas_path,
        help=f"pasta das notas (padrão: {config.notas_path})",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=config.db_path,
        help=f"arquivo SQLite (padrão: {config.db_path})",
    )
    parser.add_argument(
        "--limpar",
        action="store_true",
        help="apaga o índice antes de reindexar",
    )
    args = parser.parse_args(argv)

    if not args.notas.is_dir():
        parser.error(f"pasta de notas não encontrada: {args.notas}")

    banco = Banco(args.db)
    banco.iniciar()
    return anyio.run(_indexar, args, banco)


if __name__ == "__main__":
    raise SystemExit(main())
