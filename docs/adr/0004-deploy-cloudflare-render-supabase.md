# Deploy: Pages + Render free + Supabase, com RLS real

## Status

accepted

## Contexto

O plano (`docs/planejamento-deploy.md`) definia Render + Supabase, mas assumia
`asyncpg` + pooler. O Render free não tem disco persistente (SQLite não
serve) e o projeto Supabase não entrega a senha do banco para a API. Também
não queremos `service_role` no caminho de conversa: ela ignora RLS e
transformaria um bug de `WHERE` em vazamento entre familiares.

## Decisão

1. **Backend de dados:** PostgREST com o `access_token` do usuário. A API
   valida o JWT, extrai `sub` e repassa o token ao Supabase REST. O Postgres
   aplica as policies como `authenticated`.
2. **Validação do JWT:** JWKS (`/auth/v1/.well-known/jwks.json`) com fallback
   para `/auth/v1/user` quando o projeto ainda assina com HS256.
3. **Identidade:** `pessoas.id = sub`; `pessoa_id` não é escolhido pelo
   cliente. Endpoints por path recusam id diferente do `sub` com 403.
4. **Deploy:** Docker no Render free (sem disco), healthcheck `/health`,
   `render.yaml` versionado. PWA no Cloudflare Pages fala direto com a API.
5. **RLS:** defesa final. Todas as tabelas com policy; escritas em
   `notas`/`trechos` só com `service_role` (job de indexação).

## Consequências

- Nenhuma senha de banco no Render; o segredo mais sensível é a chave do LLM.
- RLS vale mesmo que a API erre um filtro, porque quem executa a query é o
  role `authenticated` com o JWT do usuário.
- Custo: várias chamadas HTTP por mensagem (histórico, memória, ajustes,
  contexto) e ausência de transação única. Para um grupo familiar é aceitável.
- O código mantém um backend SQLite para desenvolvimento e testes; ele só é
  escolhido quando não há `SUPABASE_URL` e `SERA_DEV=1` está definido.
- A indexação da RAG no Supabase fica fora da API, com `service_role`, para
  não expor essa chave no caminho de chat.

## Alternativas descartadas

- **asyncpg + pooler:** exigiria `DATABASE_URL` com senha no Render e um pool
  por instância; mais um segredo e mais um modo de falha.
- **service_role na API:** simples, mas fura o RLS e não é aceitável para
  memória entre familiares.
- **SQLite no Render:** o disco free é efêmero; o histórico sumiria a cada
  deploy/restart.
- **Passar pelo Pages Functions:** só adicionaria latência e um lugar a mais
  para depurar.
