# SQLite único e histórico fora do system prompt

## Status

accepted

## Decisão

A API guarda pessoas, conversas, mensagens, memórias, temas silenciados e ajustes aprendidos num único arquivo SQLite em WAL, com `PRAGMA user_version` para migrações e `ON DELETE CASCADE` a partir de `pessoas`. O system prompt continua sendo responsabilidade exclusiva da lib `sera`; a API carrega o histórico do banco, corta por janela e orçamento, e envia `[system, ...histórico, mensagem]`.

Memórias e ajustes são escritos apenas por endpoints explícitos. Não há extração automática a partir da conversa na v1: aprender por conversa é justamente o vetor que o `anti_deriva` do `personality.yaml` tenta conter, e merece um desenho próprio com revisão.

## Consequências

- Um banco só evita joins impossíveis entre conversa e pessoa e mantém o backup trivial; WAL permite leituras concorrentes com escrita serializada.
- Apagar uma pessoa apaga conversas, mensagens, memórias e ajustes em cascata — é a implementação do "esquece de verdade".
- Mensagens com status `interrompida` ou `erro` aparecem na API mas nunca entram no contexto, para o modelo não ler uma resposta truncada como se fosse dele.
- O histórico ser montado na API mantém a lib testável sem banco e permite trocar a política de janela sem tocar na personalidade.
