# RAG fase 1: índice FTS5 local, sem vetores

## Status

accepted

## Decisão

As notas Markdown entram no mesmo SQLite da API, indexadas por FTS5 (`unicode61` com `remove_diacritics 2`, porque o vault é em português), quebradas por seção `##`. A ingestão é uma CLI (`python -m sera.api.indexar`), fora do caminho da requisição, incremental por hash do arquivo: só reindexa o que mudou e remove o que sumiu.

Na busca, termos da mensagem (sem palavras vazias do português) viram uma expressão `"a" OR "b"` — nunca a string crua, que quebraria com aspas, `*` ou `NEAR`. O resultado é ordenado por `bm25` com peso maior para título e tags; resultados com score pior que 65% do melhor são descartados, porque no topo está o que interessa e a cauda só gasta orçamento. A **nota inteira** é injetada, não o trecho vencedor: com notas de ~800 caracteres, cortar em chunk só perde contexto. O padrão é no máximo 3 notas por mensagem.

O conteúdo recuperado entra como camada própria (`CONTEXTO`), entre `MEMORIA` e `REFORCO`, com orçamento em caracteres e aviso `contexto_truncado`.

## Consequências

- Vetores ficam para depois: com ~34 mil caracteres de vault, busca lexical resolve e não custa dependência nova.
- `Templates/`, `.obsidian/` e `.trash/` nunca entram no índice — template não é conhecimento.
- O índice é derivado, não fonte da verdade: `--limpar` reconstrói do zero e apagar o banco não perde nota alguma.
- Acesso ao vault é por pessoa (`pessoas.acesso_vault`), porque o vault é do dono; o padrão é liberado só para adulto e pode ser forçado nos dois sentidos.
- Busca lexical erra paráfrase ("como faço backup" não acha "cópia de segurança"). Quando isso doer, a fase 2 adiciona embeddings e funde os dois rankings por RRF, sem trocar o schema.
