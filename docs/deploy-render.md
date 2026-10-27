# Deploy — Render free + Supabase Auth/PostgREST + Cloudflare Pages

Status em 2026-10-27: schema aplicado no projeto Supabase
`zcvnfxelcgcydopcdayc`, RLS testada com dois usuários simulados, API
adaptada para JWT do Supabase e arquivos de deploy prontos.

## O que mudou em relação ao plano original

O plano previa `asyncpg` + pooler. Como o projeto Supabase não expõe a senha
do banco para a API e o objetivo é Render free com o mínimo de segredos, a
API fala com o Postgres pelo **PostgREST usando o access_token do usuário**.
Na prática:

- a API recebe `Authorization: Bearer <access_token>`;
- valida o JWT (JWKS e, se o projeto ainda usar HS256, `/auth/v1/user`);
- extrai `sub` = `pessoas.id`;
- repassa o mesmo token ao PostgREST, então o **RLS é aplicado pelo banco**;
- nunca usa `service_role` no caminho de chat.

Detalhes e trade-offs: `docs/adr/0004-deploy-cloudflare-render-supabase.md`.

## 1. Supabase (já aplicado)

Projeto: `https://zcvnfxelcgcydopcdayc.supabase.co`

Migrations versionadas em `supabase/migrations/` (`20261027000000_init.sql` e
`20261027000001_busca_titulo.sql`):

- tabelas `pessoas`, `conversas`, `mensagens`, `memorias`, `nao_mencionar`,
  `ajustes`, `notas`, `trechos`, `uso_llm`;
- `pessoas.id` referencia `auth.users(id)` com `on delete cascade`;
- RLS ligado em todas as tabelas, com policies por `auth.uid()`;
- `buscar_trechos(text, int)` para a RAG fase 1 (`tsvector` em português,
  sem acento).

Teste negativo executado no SQL (transação revertida):

- usuário A enxerga 1 pessoa, 1 conversa e 1 memória;
- usuário A enxerga 0 memórias de B;
- `authenticated` não escreve em `notas`;
- `authenticated` não cria `pessoas` com id de outro usuário.

### Auth por e-mail (OTP)

No painel do Supabase:

1. **Authentication → Providers → Email**: habilitar.
2. **Authentication → URL Configuration**: `Site URL` =
   `https://app.<seu-dominio>` (ou o domínio do Pages) e adicionar
   `https://app.<seu-dominio>/**` em Redirect URLs.
3. Para produção, configurar SMTP próprio (o e-mail de teste do Supabase tem
   limite baixo).

O PWA fará `supabase.auth.signInWithOtp({ email })` e enviará o
`access_token` para a API.

## 2. Repositório

Código em `https://github.com/AmaranthD/sera-api` (público). Segredos não
entram no repo: `.env`, `sera/api/.env` e `data/` estão no `.gitignore`.

## 3. Render (free, Docker)

O `render.yaml` já descreve o serviço:

- `runtime: docker`, `plan: free`, `region: virginia` (ajuste para a região
  mais próxima do seu projeto Supabase; o Render não tem região no Brasil);
- healthcheck `/health`;
- deploy automático a cada push em `main`;
- variáveis públicas fixas e segredos com `sync: false`.

Passos:

1. Render Dashboard → **New → Blueprint**.
2. Conectar o repositório `AmaranthD/sera-api` e aplicar.
3. Preencher os valores pedidos (`sync: false`):
   - `SUPABASE_ANON_KEY`: a publishable/anon key do projeto;
   - `LLM_API_KEY`: a chave do NVIDIA NIM (`nvapi-...`);
   - `CORS_ORIGINS`: a URL do Pages, ex. `https://sera.pages.dev`
     (o regex `*.pages.dev` já está liberado para previews).
4. Deploy. O primeiro build instala as dependências e sobe o uvicorn.

> **Free tier:** o serviço hiberna após ~15 min sem tráfego. A primeira
> mensagem do dia espera o cold start (30–60 s). Se incomodar, o plano
> Starter (~US$ 7/mês) remove a hibernação. O Supabase free pausa o projeto
> após ~7 dias sem uso.

### Verificação

```bash
curl https://sera-api.onrender.com/health
# {"status":"ok"}

# token obtido no PWA via supabase.auth.getSession()
TOKEN='<access_token>'

curl -H "Authorization: Bearer $TOKEN" \
  https://sera-api.onrender.com/pessoas

# onboarding (primeiro login) — id vem do sub, não do corpo
curl -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"nome":"Maria","faixa_etaria":"adulto"}' \
  https://sera-api.onrender.com/pessoas

# conversa em SSE
curl -N -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"mensagem":"Oi, Sera"}' \
  https://sera-api.onrender.com/chat
```

Cenários negativos esperados:

- sem `Authorization` → `401`;
- token de A pedindo `/pessoas/<id-de-B>` → `403`;
- `POST /chat` com `pessoa_id` de outra pessoa → `403`;
- conversa de outra pessoa → `404` (RLS esconde a linha).

## 4. Cloudflare Pages (PWA, depois)

Variáveis públicas do Pages:

```
VITE_SUPABASE_URL=https://zcvnfxelcgcydopcdayc.supabase.co
VITE_SUPABASE_ANON_KEY=<publishable/anon key>
VITE_API_URL=https://sera-api.onrender.com
```

Nunca colocar no Pages: `service_role`, `DATABASE_URL`, `LLM_API_KEY` ou
qualquer segredo de servidor. A `anon/publishable` é pública por desenho.

O `CORS_ORIGINS` no Render precisa bater exatamente com a origem do Pages.
Para previews, o regex `https://.*\.pages\.dev` já cobre.

## 5. O que ainda falta (fase 4)

- **Indexar notas no Supabase:** o índice é global e só `service_role`
  escreve. Fazer um job fora da API (script local ou Render Cron) que leia o
  vault e faça upsert em `notas`/`trechos`. A leitura já funciona via
  `buscar_trechos` quando houver linhas.
- **Registrar custo:** a tabela `uso_llm` existe; falta a API gravar tokens
  por mensagem.
- **Rate limit** por pessoa no `/chat`.
- **PWA:** login OTP, onboarding (`nome` + `faixa_etaria`), lista de
  conversas, SSE incremental, service worker.
