# Planejamento — Sera na nuvem (Cloudflare Pages + Render + Supabase)

> **Status em 2026-10-27:** schema e RLS aplicados no Supabase;
> backend de conversa adaptado para JWT + PostgREST (ver ADR 0004);
> Dockerfile e `render.yaml` prontos para o Render free. O passo a passo
> executável está em `docs/deploy-render.md`. A decisão de trocar `asyncpg`
> pelo PostgREST está registrada em
> `docs/adr/0004-deploy-cloudflare-render-supabase.md`.

## Objetivo

Colocar a Sera em uso diário, acessível de qualquer dispositivo, sem depender de um computador ligado em casa, mantendo três propriedades que já existem no código:

1. **Isolamento por pessoa** — a memória de um familiar nunca aparece para outro.
2. **Streaming** — a resposta chega token a token (SSE), não em bloco.
3. **Chave do LLM só no servidor** — nunca no navegador.

## Não objetivos (por enquanto)

- Multiusuário público / cadastro aberto.
- Escala horizontal, filas, múltiplas regiões.
- App nativo (o PWA cobre).
- RAG vetorial (Fase 2 do RAG; este documento só reserva espaço para `pgvector`).

---

## Arquitetura alvo

```
┌─────────────────────────────┐
│ Cloudflare Pages            │
│ PWA (HTML/JS/CSS + SW)      │
│  • login via supabase-js    │
│  • fetch + SSE para a API   │
└──────────────┬──────────────┘
               │ HTTPS + Bearer <access_token>
               ▼
┌─────────────────────────────┐        ┌──────────────────────────┐
│ Render (Docker)             │        │ Supabase                 │
│ FastAPI + uvicorn           │───────▶│  • Auth (JWT, OTP)       │
│  • valida JWT (JWKS)        │        │  • Postgres + RLS        │
│  • monta o prompt (lib)     │        │  • (futuro) pgvector     │
│  • chama o LLM (NVIDIA NIM) │        └──────────────────────────┘
│  • grava histórico/memória  │
└──────────────┬──────────────┘
               │ HTTPS
               ▼
        NVIDIA NIM (glm-5.3)
```

**Fluxo de uma mensagem**

1. PWA já tem `access_token` (renovado pelo `supabase-js`).
2. `POST {API_URL}/chat` com `Authorization: Bearer <token>` e `{mensagem, conversa_id?}`.
3. API valida o JWT (assinatura via JWKS, `iss`, `aud`, `exp`) e extrai `sub` = `pessoas.id`.
4. API abre transação no Postgres **como o usuário** (RLS ativo), lê histórico/memória/ajustes e busca trechos.
5. API monta o system prompt com `sera.prompt.montar()` e chama o NIM em streaming.
6. API repassa SSE (`event: token`) e, no fim, grava a mensagem e envia `event: done`.

**Decisão de topologia:** o PWA fala **direto** com o Render (cross-origin, com CORS restrito). Não passar por Pages Functions — só adicionaria um salto e um lugar a mais para depurar.

---

## Responsabilidades por componente

| Componente | Faz | Não faz |
|---|---|---|
| **Cloudflare Pages** | servir o shell estático, cache/offline do service worker, login, renderizar mensagens | falar com o banco, guardar chave do LLM, decidir acesso |
| **Render** | autenticar, montar prompt, chamar LLM, persistir, aplicar regras de negócio | servir arquivos estáticos |
| **Supabase Auth** | emitir/renovar JWT, magic link/OTP, sessão | decidir o que a pessoa pode ler (isso é RLS) |
| **Supabase Postgres** | dados + garantia final de isolamento via RLS | rodar lógica de prompt |
| **NVIDIA NIM** | gerar texto | guardar qualquer coisa |

---

## Autenticação

**Escolha:** magic link / OTP por e-mail (`signInWithOtp`). Sem senha para gerenciar, sem fluxo de "esqueci a senha", adequado a um grupo familiar pequeno.

**Fluxo**

1. PWA: `supabase.auth.signInWithOtp({ email })`.
2. Usuário clica no link → `supabase-js` guarda a sessão e renova o `access_token` (validade padrão ~1h).
3. Cada request leva `Authorization: Bearer <access_token>`.
4. API valida com as chaves públicas do projeto:

```
GET https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json
```

Cachear as chaves em memória (com `kid`), nunca baixar por request.

**Validar obrigatoriamente:** assinatura, `exp`, `aud = "authenticated"`, `iss = https://<ref>.supabase.co/auth/v1`, e `sub` não vazio.

**Descartar:** `SERA_API_TOKEN` (token estático). Ele deixa de existir como mecanismo de autenticação; o modelo de identidade passa a ser o usuário do Supabase.

**Provisionamento:** no primeiro login, se não existir linha em `pessoas` para aquele `sub`, a API cria com um perfil padrão (`faixa_etaria` precisa ser informada no onboarding do PWA — ela é obrigatória na lib).

> `faixa_etaria` é regra de negócio, não enfeite: ela limita sarcasmo e desliga o toque dramático em menores (`_CAPS_MENOR`). O onboarding do PWA tem que perguntar.

---

## Modelo de dados (Postgres)

Tradução do schema SQLite atual, com as mudanças necessárias.

```sql
-- identidade: 1:1 com auth.users
create table pessoas (
  id uuid primary key references auth.users(id) on delete cascade,
  nome text not null,
  faixa_etaria text not null check (faixa_etaria in ('adulto','adolescente','crianca')),
  perfil text not null default 'padrao'
    check (perfil in ('padrao','crianca_adolescente','idoso_ou_pouco_tecnico')),
  criada_em timestamptz not null default now()
);

create table conversas (
  id uuid primary key default gen_random_uuid(),
  pessoa_id uuid not null references pessoas(id) on delete cascade,
  titulo text,
  criada_em timestamptz not null default now(),
  atualizada_em timestamptz not null default now()
);
create index on conversas (pessoa_id, atualizada_em desc);

create table mensagens (
  id uuid primary key default gen_random_uuid(),
  conversa_id uuid not null references conversas(id) on delete cascade,
  papel text not null check (papel in ('user','assistant')),
  conteudo text not null,
  status text not null default 'completa'
    check (status in ('completa','interrompida','erro')),
  criada_em timestamptz not null default now()
);
create index on mensagens (conversa_id, criada_em);

create table memorias (
  id uuid primary key default gen_random_uuid(),
  pessoa_id uuid not null references pessoas(id) on delete cascade,
  texto text not null,
  categoria text not null default 'outro'
    check (categoria in ('familia','trabalho','gostos','rotina','saude','outro')),
  criada_em timestamptz not null default now()
);
create index on memorias (pessoa_id);

create table nao_mencionar (
  pessoa_id uuid not null references pessoas(id) on delete cascade,
  tema text not null,
  primary key (pessoa_id, tema)
);

create table ajustes (
  id uuid primary key default gen_random_uuid(),
  pessoa_id uuid not null references pessoas(id) on delete cascade,
  tipo text not null check (tipo in (
    'apelido','piada_interna','formato','assunto',
    'nivel_sarcasmo','formalidade','nivel_tecnico','toque_yandere'
  )),
  texto text,
  valor text,
  origem text not null check (origem in ('conversa','manual')),
  criada_em timestamptz not null default now()
);
create index on ajustes (pessoa_id);

-- RAG fase 1 (substitui notas/trechos/trechos_fts)
create table notas (
  id uuid primary key default gen_random_uuid(),
  caminho text not null unique,
  titulo text not null,
  tags text[] not null default '{}',
  hash text not null,
  atualizada_em timestamptz not null default now()
);

create table trechos (
  id bigserial primary key,
  nota_id uuid not null references notas(id) on delete cascade,
  ordem int not null,
  secao text not null,
  texto text not null,
  busca tsvector generated always as (
    to_tsvector('portuguese', coalesce(secao,'') || ' ' || coalesce(texto,''))
  ) stored
);
create index on trechos using gin (busca);
create index on trechos (nota_id, ordem);
```

**Busca** (Fase 1, equivalente ao FTS5):

```sql
select t.*, ts_rank(t.busca, q) as score
from trechos t, websearch_to_tsquery('portuguese', unaccent($1)) q
where t.busca @@ q
order by score desc
limit 20;
```

Requer `create extension if not exists unaccent;` e o `tsvector` sobre texto **sem acento** (ou um `unaccent` na geração, que não é imutável — nesse caso use `to_tsvector('portuguese', unaccent(...))` dentro de uma trigger em vez de coluna gerada).

> Ajuste fino fica em aberto: `portuguese` faz stemming (bom para recall), mas muda o comportamento vs. o `unicode61 remove_diacritics 2` atual. Validar com um conjunto golden de 20 perguntas antes de considerar pronto.

**Pendente de decisão:** dimensão `colecao` para indexar outras fontes (PDF, e-mail, código). Recomendação registrada: **um índice só, com coluna `colecao`**, não um RAG por fonte. Entra como migração própria, depois que este deploy estiver estável.

---

## Isolamento: RLS

RLS ligado em **todas** as tabelas. Nenhuma exceção.

```sql
alter table pessoas enable row level security;
create policy pessoa_propria on pessoas
  for all using (id = auth.uid()) with check (id = auth.uid());

alter table conversas enable row level security;
create policy conversa_propria on conversas
  for all using (pessoa_id = auth.uid()) with check (pessoa_id = auth.uid());

alter table mensagens enable row level security;
create policy mensagem_propria on mensagens for all
  using (exists (select 1 from conversas c
                 where c.id = conversa_id and c.pessoa_id = auth.uid()))
  with check (exists (select 1 from conversas c
                      where c.id = conversa_id and c.pessoa_id = auth.uid()));

-- repetir o padrão pessoa_id = auth.uid() em memorias, nao_mencionar, ajustes
```

**Como o RLS realmente vale na API.** RLS só se aplica se a conexão não for dona das tabelas e não tiver `BYPASSRLS`. Duas opções:

- **A — Recomendada:** a cada request, abrir transação e executar, antes das queries:

```sql
select set_config('request.jwt.claims',
                  json_build_object('sub', $1, 'role', 'authenticated')::text, true);
set local role authenticated;
```

  Assim o Postgres aplica as policies por usuário **mesmo que a API tenha um bug de `WHERE`**. É a única forma de o RLS ser defesa real e não decoração.

- **B — Fallback:** conectar com um role dedicado sem `BYPASSRLS` e **sempre** filtrar por `pessoa_id = sub` no código. Funciona, mas o RLS passa a ser inútil (nenhuma policy casa com o role). Só aceite se A se mostrar inviável com o driver.

**Teste obrigatório antes do deploy:** autenticar como usuário A e tentar ler conversa/memória do usuário B direto pela API e pelo PostgREST. Precisa devolver 0 linhas / 403.

---

## Mudanças no código

### Não muda

- `sera/prompt/**` — a lib é agnóstica de banco.
- `personality.yaml`, `GLOSSARY.md`, os ADRs 0001–0003.
- O contrato do `/chat` (SSE `token`/`done`/`error`) e dos demais endpoints.
- A semântica de status (`completa`/`interrompida`/`erro`) e o corte de histórico.

### Muda

| Arquivo | Mudança |
|---|---|
| `sera/api/db.py` | reescrita: `sqlite3` → `asyncpg` + pool (usar o **pooler** do Supabase, porta 6543). Manter os **mesmos nomes de método** (`obter_pessoa`, `listar_ajustes`, `buscar_trechos`…) para `rotas.py` quase não mudar |
| `sera/api/config.py` | saem `db_path`, `api_token`; entram `database_url`, `supabase_url`, `supabase_jwt_aud`, `cors_origins` |
| `sera/api/rotas.py` | dependência `usuario_atual` (JWT) no lugar de `_exigir_token`; `pessoa_id` deixa de vir do corpo (vem do `sub`) |
| `sera/api/schemas.py` | `Slug` → `UUID`; `ChatEntrada` perde `pessoa_id` (ou vira opcional e precisa bater com o `sub`) |
| `sera/api/indexar.py` | passa a gravar no Postgres; vira job (Render Cron) em vez de CLI manual |
| `tests/**` | os testes de API deixam de usar `tmp_path`/SQLite; precisam de Postgres (testcontainers ou branch do Supabase) |
| `sera/api/app.py` | `CORSMiddleware` com origin exato do Pages; healthcheck já existe |

**Ponto de atenção:** hoje `PessoaEntrada.id` é um slug legível e o `pessoa_id` viaja no corpo do `/chat`. Com identidade real, **`pessoa_id` não pode ser escolhido pelo cliente** — senão qualquer pessoa autenticada conversa como outra. O `sub` do JWT é a única fonte.

### Configuração (variáveis de ambiente)

**Render**

```
DATABASE_URL=postgresql://...@aws-0-<região>.pooler.supabase.com:6543/postgres
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_JWT_AUD=authenticated
LLM_PROVIDER=openai
LLM_BASE_URL=https://integrate.api.nvidia.com/v1
LLM_API_KEY=<nvapi-...>
LLM_MODEL=z-ai/glm-5.3
LLM_MAX_TOKENS=4096
CORS_ORIGINS=https://app.<dominio>
SERA_NOTAS=/app/notas
```

**Cloudflare Pages** (públicas por definição — só a `anon key`)

```
VITE_SUPABASE_URL=https://<ref>.supabase.co
VITE_SUPABASE_ANON_KEY=<anon/publishable>
VITE_API_URL=https://api.<dominio>
```

Nunca colocar `service_role`, `DATABASE_URL` ou `LLM_API_KEY` no Pages.

---

## Infra e operação

| Item | Decisão |
|---|---|
| Região | Render e Supabase na **mesma região** (ex.: `us-east`/`eu-central`); evita ~150 ms por consulta |
| Render | Docker, 1 instância, healthcheck `/health`, deploy automático no `main` |
| Pool | Supabase pooler em modo transação; pool pequeno (5–10) por instância |
| Cloudflare Pages | build Vite, `_redirects` com fallback SPA, cache do shell no service worker |
| Domínio | `app.<dominio>` (Pages) e `api.<dominio>` (Render) |
| Migrações | SQL versionado no repo + `supabase db push` (ou `migra`) — não editar schema pelo painel |
| Backup | PITR/backup do Supabase; export lógico semanal é barato e cobre "errei uma migração" |
| Observabilidade | logs do Render + tabela `uso_llm` (pessoa, tokens, modelo, dia) para controlar custo por pessoa |
| Limites | rate limit por usuário no `/chat` (ex.: 60 req/h) — com login aberto, abuso vira custo |

### Custos (confirmar valores atuais antes de fechar)

| Serviço | Plano | Observação |
|---|---|---|
| Cloudflare Pages | Free | bandwidth/requests livres; limite de builds/mês |
| Supabase | Free (500 MB) | **pausa o projeto após ~7 dias sem uso** |
| Render | Starter ~US$ 7/mês | free hiberna em ~15 min → primeira mensagem do dia lenta |

Custo total realista: **~US$ 7/mês + tokens do LLM**. Se o objetivo for zero, Render free + Supabase free funcionam, aceitando hibernação e pausa.

---

## Fases

### Fase 0 — Decisões (antes de escrever código)
- [ ] Região do Supabase e do Render (mesma)
- [ ] Domínio e subdomínios
- [ ] OTP por e-mail vs. senha (recomendado: OTP)
- [ ] Quem pode ser criado: onboarding aberto ou lista fechada de e-mails
- [ ] Política de retenção: apagar pessoa apaga histórico e memória; backups guardam por N dias

### Fase 1 — Supabase
- [ ] Projeto criado na região escolhida
- [ ] Schema aplicado por migração versionada
- [ ] RLS ligado + policies + teste negativo (usuário A não lê B)
- [ ] Auth por OTP com redirect para `app.<dominio>`
- [ ] JWKS acessível e cacheado pela API

**Critério de aceite:** dois usuários de teste, cada um só enxerga as próprias linhas, comprovado por SQL direto e por chamada à API.

### Fase 2 — Backend
- [ ] `db.py` reescrito para `asyncpg` mantendo a interface pública
- [ ] Dependência `usuario_atual` (JWKS) substituindo `SERA_API_TOKEN`
- [ ] `pessoa_id` removido do corpo do `/chat`
- [ ] `CORSMiddleware` restrito ao origin do Pages
- [ ] `Dockerfile` + healthcheck
- [ ] Testes de API rodando contra Postgres (container ou branch)
- [ ] Suíte completa verde, incluindo o teste de isolamento

**Critério de aceite:** `curl` sem token → 401; com token de A pedindo conversa de B → 404/403; streaming continua funcionando.

### Fase 3 — PWA

Detalhamento executável em `docs/planejamento-front.md`.

- [x] Login (OTP) e persistência de sessão
- [x] Onboarding: nome + faixa etária (obrigatório)
- [x] Lista de conversas, abrir conversa, enviar mensagem
- [x] Consumo de SSE com render incremental e botão de interromper
- [x] Shell offline (abre sem rede; enviar exige rede)
- [x] Instalável (manifest + ícones + service worker)

**Critério de aceite:** conversa completa no celular, resposta aparecendo token a token, recarregar mantém o histórico.

### Fase 4 — Deploy e operação
- [ ] Domínios e TLS (ambos automáticos)
- [ ] Indexar notas no deploy (`python -m sera.api.indexar`) e validar busca
- [ ] Backup/export testado (restaurar em um projeto de teste)
- [ ] Tabela `uso_llm` + alerta de custo
- [ ] Rate limit por usuário

**Critério de aceite:** derrubar o Supabase de teste e restaurar o backup dentro do RPO combinado.

### Fase 5 — (depois) RAG fase 2 e coleções
- [ ] `pgvector` + embeddings (`nvidia/nemotron-3.5-embed-1b`, 2048 dims)
- [ ] Fusão híbrida (RRF) entre `tsvector` e vetor
- [ ] Dimensão `colecao` + `acesso_colecao` por pessoa
- [ ] Conector de PDF/e-mail conforme demanda

---

## Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| RLS mal configurado | vazamento de memória entre familiares | teste negativo obrigatório na Fase 1; conexão como `authenticated` |
| `pessoa_id` aceito do cliente | personificação | derivar sempre do `sub`; remover do schema de entrada |
| Hibernação do Render | primeira mensagem do dia lenta | plano Starter ou ping de keep-alive |
| Pausa do Supabase free | app fora até reativar | uso diário basta; monitorar |
| Latência entre regiões | respostas mais lentas | Render e Supabase na mesma região |
| Custo do LLM por abuso | fatura inesperada | rate limit + `uso_llm` + teto por pessoa |
| Migração de schema manual | drift entre ambientes | migrações no repo, nunca no painel |
| "Esquece de verdade" | linhas sobrevivem em backup | documentar retenção e janela de PITR |
| Dados da família em terceiros | privacidade | registrar no ADR; opção de API em casa via Cloudflare Tunnel |

---

## ADR a escrever quando a decisão for tomada

`docs/adr/0004-deploy-cloudflare-render-supabase.md`, contendo: por que não Netlify/Vercel (Python + disco + timeout), por que Postgres no lugar de SQLite, por que o navegador não fala com o banco, e a escolha de RLS como barreira final.
