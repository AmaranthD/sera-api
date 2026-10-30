# Planejamento — front (PWA) no Cloudflare Pages conectado à API

> **Status em 2026-10-29:** fases 0 a 3 implementadas em `web/` e verificadas
> com lint, typecheck, 57 testes unitários/componente, 6 E2E e build de
> produção. O que depende de conta externa — criar o projeto no Cloudflare
> Pages, configurar Redirect URLs de produção e rodar a matriz manual de
> aparelhos — continua pendente e está marcado nas fases. Decisões fechadas:
> React + TypeScript + Vite, código em `web/` no mesmo repositório e escopo
> da Fase 3 do `docs/planejamento-deploy.md` (login, onboarding, conversas,
> SSE, PWA). O backend já está pronto para JWT + PostgREST (ADR 0004); este
> documento registra o contrato e o que falta do lado do navegador.

## Objetivo

Entregar um PWA instalável, mobile-first, que usa a API existente sem
intermediários:

1. Login por OTP (magic link) via Supabase Auth.
2. Onboarding obrigatório (`nome` + `faixa_etaria`).
3. Lista de conversas, abrir histórico e enviar mensagens.
4. Streaming token a token com botão de interromper.
5. Shell offline e instalável, sem guardar conteúdo de conversa no
   dispositivo.

Critério geral: uma pessoa da família consegue conversar no celular, do
primeiro login ao histórico recarregado, sem instrução técnica.

## Não objetivos (nesta fase)

- Telas de memória, temas silenciados e botões de estilo (Fase 4).
- Editar/apagar conversa e renomear título pela interface.
- Markdown rico nas respostas; o MVP renderiza texto puro com quebras
  preservadas.
- Funcionar offline para **enviar** ou **ler histórico**.
- Analytics, push notification, app nativo, multiusuário público.
- Pages Functions como proxy; o navegador fala direto com o Render.

---

## Arquitetura

```
┌──────────────────────────────────────────┐
│ Cloudflare Pages (estático)              │
│  React + Vite + PWA                      │
│  • supabase-js: login, sessão, refresh   │
│  • fetch + ReadableStream: /chat (SSE)   │
│  • service worker: apenas o shell        │
└───────────────┬──────────────────────────┘
                │ HTTPS + Bearer <access_token>
                │ CORS: origin exato (+ previews)
                ▼
┌──────────────────────────────────────────┐        ┌─────────────────────┐
│ Render: FastAPI (já existe)              │───────▶│ Supabase Auth       │
│  valida JWT, monta prompt, persiste      │        │  (JWKS / OTP)       │
└──────────────────────────────────────────┘        └─────────────────────┘
```

Sem Pages Functions, sem proxy, sem `service_role` no navegador. A única
chave no front é a `anon/publishable`, que é pública por desenho.

### Contrato usado pelo front

| Método | Rota | Uso |
|---|---|---|
| `POST` | `/pessoas` | onboarding (id vem do `sub`) |
| `GET` | `/pessoas` | detectar se já fez onboarding |
| `GET` | `/pessoas/{id}/conversas` | lista lateral |
| `GET` | `/conversas/{id}/mensagens` | abrir histórico |
| `POST` | `/chat` | enviar mensagem; SSE `start`/`token`/`done`/`error` |
| `GET` | `/health` | indicador de API acordada |

Todos com `Authorization: Bearer <access_token>`, exceto `/health`.

**Formato do SSE (implementado):**

```
event: start
data: {"conversa_id":"...","mensagem_id":"..."}

event: token
data: {"texto":"..."}

event: done
data: {"conversa_id":"...","mensagem_id":"...","modelo":"...","uso":{...}}

event: error
data: {"codigo":"llm_falhou","detalhe":"..."}
```

---

## Lacunas do backend que o front expõe

G1 e G2 foram resolvidos junto com a Fase 0; as demais continuam fora do MVP.

| # | Lacuna | Impacto | Correção proposta |
|---|---|---|---|
| G1 | O SSE não informa `conversa_id` no início, só no `done` | ao criar conversa nova e interromper/perder rede antes do `done`, o front não sabe qual conversa recarregar; a mensagem do usuário já foi gravada | **feito:** `event: start` com `conversa_id` e `mensagem_id` (mensagem do usuário) antes do primeiro `token`; teste em `tests/api/test_chat.py` |
| G2 | `conversas.titulo` nasce `null` e nunca é preenchido | lista lateral vira "Conversa de 27/10" e depende de abrir para saber o assunto | **feito:** o `/chat` grava `titulo` com os primeiros ~60 caracteres da mensagem, normalizando espaços; teste de contrato |
| G3 | não há `PATCH /pessoas/{id}` | configurações só leem nome/faixa etária | fora do MVP; tela de conta read-only + logout |
| G4 | não há `DELETE /conversas/{id}` nem rename | não dá para limpar conversa antiga | Fase 4; não improvisar chamada direta ao PostgREST no front |
| G5 | CORS libera `GET/POST/DELETE/OPTIONS` | se entrar `PATCH`, o preflight falha | incluir `PATCH` em `allow_methods` junto com G3 |
| G6 | sem rate limit / 429 | abuso vira custo de LLM | tratar 429 com mensagem clara; rate limit é Fase 4 |

> G1 e G2 são mudanças pequenas em `sera/api/rotas.py` + testes. Faça-as
> junto com a Fase 0 do front para não cristalizar um contrato ruim.

**Comportamento já garantido pelo backend:** `pessoa_id` nunca vem do
cliente; conversa de outra pessoa retorna 404; interrupção grava a resposta
parcial com status `interrompida`; RLS é a barreira final.

---

## Stack e estrutura

**Decisões:**

- **React + TypeScript + Vite**, SPA, sem SSR (Pages é estático).
- **supabase-js** só para Auth. O banco continua atrás da API.
- **React Router** com `BrowserRouter` (rotas reais + `_redirects`).
- **CSS Modules + tokens** (`src/estilos/global.css`), sem UI kit e sem
  Tailwind. Menos dependências, controle fino de contraste e alvo de toque.
- **Sem TanStack Query** no MVP: um `api/` fino + hooks explícitos por tela.
  O estado de servidor é pequeno e o fluxo de chat precisa de controle manual.
- **`vite-plugin-pwa`** (Workbox) para manifest + service worker.
- **Vitest + Testing Library + MSW** para unidade/integração e **Playwright**
  para o caminho feliz.
- Node 22 no Pages e no CI (o Node 18 local está EOL e não roda Vite atual).

```
web/
├── index.html
├── package.json
├── package-lock.json
├── tsconfig.json
├── vite.config.ts             # React, PWA e Vitest
├── playwright.config.ts
├── eslint.config.js
├── .nvmrc                     # 22
├── .env.example
├── scripts/
│   ├── gerar-icones.mjs       # PNGs a partir do favicon.svg
│   └── gerar-headers.mjs      # dist/_headers com CSP
├── public/
│   ├── _redirects             # /* /index.html 200
│   ├── favicon.svg
│   ├── robots.txt
│   └── icons/                 # 192, 512, maskable, apple-touch
├── e2e/
│   ├── ajuda.ts               # sessão Supabase falsa + rotas da API
│   └── chat.spec.ts
└── src/
    ├── main.tsx
    ├── App.tsx                # rotas e providers
    ├── env.ts                 # valida VITE_* no boot (falha cedo)
    ├── auth/
    │   ├── SessaoProvider.tsx # supabase-js, OTP, refresh, logout
    │   ├── contexto.ts
    │   └── supabase.ts
    ├── api/
    │   ├── http.ts            # fetch + Bearer + timeout + refresh 1x
    │   ├── erros.ts
    │   ├── sse.ts             # parser de SSE (função pura)
    │   ├── chat.ts            # POST /chat em streaming
    │   └── sera.ts            # pessoas, conversas, mensagens
    ├── dominios/
    │   ├── tipos.ts
    │   └── texto.ts           # título, datas, grupos, nomes
    ├── pessoa/                # carrega/cria a pessoa do onboarding
    ├── chat/                  # ChatProvider: stream, abort, URL
    ├── telas/
    │   ├── login/
    │   ├── onboarding/
    │   ├── chat/              # shell, lista, drawer, mensagens, composer
    │   └── conta/
    ├── componentes/           # botão, campo, banner, marca, ícones…
    ├── pwa/                   # online/offline e instalação
    ├── estilos/global.css     # tokens, reset e utilidades
    └── test/setup.ts
```

A implementação manteve a regra de dependência planejada: `telas →
contexto/providers → api`; nada em `api/` importa React. A CSP não é um
`public/_headers` estático: `scripts/gerar-headers.mjs` a gera no pós-build
com os hosts reais, para não versionar endereços de produção.

**Regra de dependência:** `telas → hooks/api → api/http`; nada em `api/`
importa React. `sse.ts` é puro e testável sem navegador. Isso mantém o
parser e o contrato isolados da UI.

### Variáveis de ambiente (build time, públicas)

```bash
VITE_SUPABASE_URL=https://zcvnfxelcgcydopcdayc.supabase.co
VITE_SUPABASE_ANON_KEY=<publishable/anon key>
VITE_API_URL=https://sera-api.onrender.com
```

`env.ts` valida presença e formato (URL https, sem barra final) e derruba o
build se faltar. Nunca colocar `service_role`, `DATABASE_URL` ou
`LLM_API_KEY` aqui.

---

## Autenticação e sessão

**Fluxo**

1. `/login`: campo de e-mail → `supabase.auth.signInWithOtp({ email,
   options: { emailRedirectTo: window.location.origin + '/' } })`.
2. Tela "Enviamos um link" com reenvio (cooldown 60 s) e troca de e-mail.
3. O link volta para a origem com `?code=...` (PKCE). O `supabase-js` cria a
   sessão (`flowType: 'pkce'`, `detectSessionInUrl: true`).
4. `SessaoProvider` expõe `session` e um `obterToken()` que chama
   `getSession()` antes de cada request (renova se estiver perto de expirar).
5. Sem sessão → `/login`. Com sessão e sem pessoa → `/onboarding`. Com
   pessoa → `/`.

**Regras**

- `onAuthStateChange` sincroniza logout entre abas e limpa caches em memória.
- `SIGNED_OUT` ou `401` da API → volta ao login com aviso "sessão expirou",
  preservando o e-mail digitado.
- Em `401`, tentar `refreshSession()` **uma vez** e repetir a requisição;
  se falhar, encerrar a sessão local.
- Nunca interpretar o JWT no front para decidir permissão; o `sub` só é útil
  para diagnóstico. Quem manda é a API.
- Erros de link expirado/ inválido (`error`, `error_description` na URL)
  ganham tela própria com "pedir novo link".

**Configuração no Supabase:** `Site URL` e `Redirect URLs` precisam incluir
a origem de produção (`https://app.<dominio>/**`) e, se for testar login em
preview, `https://<projeto>*.pages.dev/**`. Sem isso o magic link cai na
página errada.

---

## Onboarding

Uma tela, três campos, sem cadastro separado:

| Campo | Regra | Origem |
|---|---|---|
| `nome` | 1–80 caracteres, `trim` | livre |
| `faixa_etaria` | `adulto` \| `adolescente` \| `crianca` | obrigatório |
| `perfil` | `padrao` \| `crianca_adolescente` \| `idoso_ou_pouco_tecnico` | cards com descrição humana |

- `perfil` vem pré-selecionado: menor → `crianca_adolescente`; demais →
  `padrao`. A pessoa pode trocar; o texto explica o efeito ("mais direto",
  "mais paciente e explicadinho").
- `acesso_vault` não aparece no MVP; o backend já deriva de `faixa_etaria`
  quando o campo é omitido.
- `POST /pessoas` com o token; `409` significa que outra aba já criou →
  recarregar `GET /pessoas` e seguir.
- Depois do sucesso, guardar a pessoa no contexto e ir para `/`.

**Acessibilidade:** os cards de perfil são `radio` de verdade (teclado e
leitor de tela), não `div` clicável.

---

## Telas e estados

### Shell do chat

- **Desktop:** sidebar de 320 px (nome da Sera, "Nova conversa", lista) +
  área de conversa.
- **Mobile:** uma coluna; lista em drawer acessível por botão no topo.
- Header mostra o nome da pessoa e um menu com "Conta" e "Sair".
- Composer fixo no rodapé, respeitando `env(safe-area-inset-bottom)`.
- Fonte base 18 px, alvos de toque ≥ 48 px, contraste AA. Nada de texto
  cinza claro em fundo claro.

### Lista de conversas

- `GET /pessoas/{id}/conversas`, ordenada por `atualizada_em` (a API já
  ordena).
- Título: `titulo` (após G2) ou, enquanto não houver, "Conversa de
  dd/mm HH:mm". Nunca inventar título a partir do histórico no cliente.
- Agrupamento por "Hoje", "Ontem", "Últimos 7 dias", "Mais antigas".
- Item ativo destacado; foco visível.
- Empty state com uma sugestão de primeira mensagem ("Conte como foi seu
  dia") — sem simular conversa.

### Conversa

- Carrega `GET /conversas/{id}/mensagens`; rola para o fim após render.
- Mensagens do usuário e da assistente com tratamento visual distinto;
  `status = interrompida` ganha marca discreta ("resposta interrompida");
  `erro` idem.
- Texto puro com `white-space: pre-wrap` (sem `dangerouslySetInnerHTML`).
- Enquanto transmite: cursor/indicador, botão "Parar" no lugar de "Enviar",
  composer bloqueado.
- `aria-live="polite"` em um nó que recebe o texto final (não cada token,
  para não inundar o leitor de tela).
- Auto-scroll só se a pessoa já estava no fim; se rolou para cima, mostrar
  botão "Ir para o fim".

### Estados de envio (máquina explícita)

```
idle → enviando → transmitindo → concluido
                        ├─ interrompido (abort)
                        ├─ erro (event: error ou rede)
                        └─ sessao_expirada (401)
```

- `enviando`: request aberta, ainda sem primeiro byte. Após 8 s, mostrar
  "A Sera está acordando…" (Render free hiberna). Timeout total de 120 s
  para o primeiro byte, sem timeout no meio do stream.
- `transmitindo`: tokens sendo anexados.
- Interromper: `AbortController.abort()`. O backend grava a parcial como
  `interrompida`; o front mantém o texto já recebido e marca a mensagem.
- Erro de rede: preservar o texto parcial, oferecer "Tentar de novo" (nova
  mensagem, não reenvio automático — evita duplicar).
- `done`: atualizar ids, invalidar a lista de conversas e permitir nova
  mensagem.
- Duplo clique/Enter repetido não pode abrir dois streams.

### Conta

Read-only no MVP: e-mail da sessão, nome e faixa etária (de `GET
/pessoas`), estado da API (`/health`), botão "Sair". Edição fica para quando
existir G3.

---

## Cliente HTTP e SSE

### `api/http.ts`

- Base URL de `env.ts`; sempre `Authorization: Bearer` obtido de
  `obterToken()`.
- Mapear erro para um tipo único: `{ status, codigo, mensagem }`.
  - `401` → sessão expirada (refresh 1x).
  - `403` → "sem acesso".
  - `404` → "não encontrado" (conversa de outra pessoa cai aqui).
  - `422` → mostrar `detail` da API (validação).
  - `429` → "muitas mensagens em pouco tempo".
  - `5xx`/rede → "A Sera não respondeu" + tentar de novo.
- Não logar token nem conteúdo de mensagem.

### `api/sse.ts` (função pura)

- `POST` com `fetch`, `Accept: text/event-stream`, `body` JSON.
- Antes de ler o corpo: se `!response.ok`, ler JSON de erro (a API devolve
  `HTTPException` em JSON, não SSE) e lançar o erro mapeado.
- Ler `response.body.getReader()` com `TextDecoder(stream: true)`.
- Acumular buffer e separar eventos por linha em branco, aceitando `\n` e
  `\r\n`; juntar `data:` de múltiplas linhas com `\n`.
- Ignorar comentários (`:`), campos desconhecidos e `retry:`.
- Entregar `{ evento, dados }` para o chamador; `JSON.parse` com try/catch
  (evento malformado vira erro de protocolo, não quebra a tela).
- No `finally`, cancelar o reader e limpar o buffer.
- **Testes obrigatórios:** frame partido entre chunks, UTF-8 partido no meio
  de acento, `\r\n`, múltiplos eventos no mesmo chunk, `data:` multilinha,
  `error` e fim abrupto sem `done`.

### Interrupção

- `AbortSignal` propagado ao `fetch`. Abortar fecha a conexão; o FastAPI
  detecta `request.is_disconnected()` e grava `interrompida`.
- Não usar `EventSource` (não faz POST nem manda `Authorization`).

---

## PWA e offline

- `vite-plugin-pwa` com `registerType: 'autoUpdate'`, manifest
  (`name: Sera`, `short_name: Sera`, `lang: pt-BR`, `display: standalone`,
  `start_url: /`, tema/cores, ícones 192/512 + maskable).
- **Precache:** apenas assets do build + `index.html`.
- **Navegação:** fallback para `/index.html` (SPA).
- **Nunca cachear:** `/chat`, chamadas ao Supabase, `/health`, qualquer
  resposta com dados de pessoa. Requisições cross-origin ficam fora do
  service worker.
- **Sem cache de mensagens no dispositivo** por padrão. Conteúdo de
  conversa é sensível; um tablet compartilhado não deve guardar histórico.
  Offline = shell abre, mostra banner "sem conexão", composer desabilitado.
  A única exceção é o **perfil mínimo** (nome, faixa etária e perfil),
  guardado em `localStorage` com a chave `sera.pessoa.v1` e amarrado ao id
  da sessão, para o shell abrir sem rede; ele é limpo no logout e em 401.
  Se um dia houver cache de conversa, será opt-in explícito e com botão de
  limpar.
- Atualização: banner "Nova versão disponível" + recarregar; não trocar o
  SW no meio de um stream.
- Instalação: botão "Instalar app" quando `beforeinstallprompt` existir;
  no iOS, instrução curta "Compartilhar → Adicionar à Tela de Início".
- Testar o link mágico com o SW ativo: a navegação para `/?code=...` não
  pode servir uma cópia velha do shell que perca o código.

---

## Cloudflare Pages

**Projeto:** Git integration no repo `AmaranthD/sera-api`.

| Configuração | Valor |
|---|---|
| Production branch | `main` |
| Root directory | `web` |
| Build command | `npm ci && npm run build` |
| Output directory | `dist` |
| Node version | `22` (env `NODE_VERSION=22` ou `.nvmrc`) |
| Variáveis | `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_URL` |

> O Node 18 da máquina local não roda o Vite atual. Suba para Node 22 antes
> de iniciar o front (ou use `nvm`/`fnm`). O build do Pages já usa 22.

**`web/public/_redirects`**

```
/*    /index.html    200
```

**`web/public/_headers` (produção)**

```
/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: no-referrer
  Permissions-Policy: geolocation=(), microphone=(), camera=()
  Content-Security-Policy: default-src 'self'; connect-src 'self' https://<ref>.supabase.co https://<api-host>; img-src 'self' data:; style-src 'self'; font-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'
```

- CSP só em produção; o dev server do Vite injeta script inline e quebraria.
- Se as fontes forem do sistema (recomendado), nenhum domínio externo de
  fonte entra na CSP. Sem Google Fonts: mais rápido e sem vazamento.
- `connect-src` precisa listar Supabase e API; qualquer coisa nova (ex.:
  Sentry) exige atualizar a CSP junto.

**Preview deployments:** o `CORS_ORIGIN_REGEX` do Render já cobre
`*.pages.dev`, mas ele é amplo. Preferir uma origem de produção exata em
`CORS_ORIGINS` e, se previews forem usados com dados reais, criar um
projeto Pages separado com allowlist mais estreita. Para login em preview,
adicionar a URL de preview nas Redirect URLs do Supabase.

**Domínio:** `app.<dominio>` (Pages) e `api.<dominio>` (Render). TLS
automático nos dois. Ao trocar para domínio próprio:

1. DNS do Pages + custom domain.
2. `CORS_ORIGINS=https://app.<dominio>` no Render.
3. `Site URL` + Redirect URLs no Supabase.
4. Rebuild do Pages (as `VITE_*` mudam só se a API mudar de host).

**Deploy manual (fallback):** `npx wrangler pages deploy dist --project-name sera`
— útil para testar um build local sem push. Não é o fluxo principal.

---

## Testes

| Nível | Ferramenta | Cobertura mínima |
|---|---|---|
| Unidade | Vitest | parser SSE (casos acima), montagem de URL/headers, derivação de título/data, validação de onboarding, máquina de estados do envio |
| Componente | Testing Library + MSW | login (envio/erro/cooldown), onboarding (409), lista vazia, histórico, stream com abort, 401 → login |
| E2E | Playwright | login mockado → onboarding → primeira mensagem em stream → recarregar → histórico; offline mostra banner; manifest/SW registrados |
| A11y | axe (no Playwright ou Vitest) | login, onboarding e chat sem violações sérias; navegação só por teclado |
| Manual | matriz de dispositivos | iOS Safari (PWA), Android Chrome, desktop; 3G lento; cold start do Render; link mágico com SW ativo |

- Arena de testes implementada: 57 testes Vitest (parser, HTTP, contrato,
  domínio, login, onboarding e componentes) e 6 E2E Playwright com Supabase
  falso. A matriz de dispositivo e o axe automatizado continuam
  manuais/pendentes.
- MSW simula `text/event-stream` com chunks controlados (inclusive atraso
  para testar "acordando"). O E2E usa `page.route` e uma sessão Supabase
  falsa em `localStorage`; nada sai para a rede.
- O backend em `SERA_DEV=1` usa SQLite e **não** exercita JWT; para E2E de
  integração real, usar um projeto Supabase de teste ou rodar a API com
  PostgREST falso. O caminho padrão de CI é MSW; integração real é smoke
  manual antes do deploy.
- CI em `.github/workflows/web.yml`: em PR e push na `main`, `npm ci`,
  `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm test`,
  `npm run build` e Playwright em Node 22. Deploy fica com o Pages.

---

## Notas de implementação (2026-10-29)

- A CSP é gerada por `web/scripts/gerar-headers.mjs` no pós-build, não por um
  `_headers` estático; hosts de produção não entram no repositório.
- Cabeçalho do chat mostra o título da conversa e um atalho para a conta; o
  nome completo e "Conta e ajustes" ficam no rodapé da sidebar (no mobile,
  avatar no header e drawer).
- Os estados internos do envio são `ocioso`, `enviando`, `transmitindo` e
  `erro`; interrupção volta para `ocioso` mantendo o texto parcial.
- O fallback de título para conversas antigas é "Conversa de dd/mm HH:mm"
  (linhas criadas antes do G2).
- O E2E encontrou e corrigiu uma corrida no boot: o perfil precisava esperar
  a leitura da sessão do Supabase antes de decidir que não havia pessoa, ou
  `/conta` desviava para `/onboarding` e voltava para `/`.

## Fases

### Fase 0 — Contrato e scaffold

- [x] G1: `event: start` no SSE + teste
- [x] G2: título da conversa na criação + teste
- [x] `web/` com Vite + React + TS, Node 22, lint/format, Vitest
- [x] `env.ts`, `api/http.ts`, `api/sse.ts` com testes
- [x] `_redirects`, `_headers` (gerado no build), manifest e ícones
- [x] CI de PR (`.github/workflows/web.yml`)

**Aceite:** `npm run build` verde; parser SSE passa nos casos de borda;
`curl -N` mostra `start` antes do primeiro `token`.

### Fase 1 — Login e onboarding

- [x] Tela de login OTP + reenvio + estados de erro
- [x] `SessaoProvider` com refresh e logout entre abas
- [x] Guarda de rotas (login/onboarding/app)
- [x] Onboarding com validação e `409`
- [x] Conta read-only + sair
- [ ] Configurar Supabase Redirect URLs de dev e produção (depende do
      projeto/credenciais reais; ver `docs/deploy-cloudflare-pages.md`)

**Aceite:** e-mail recebido, link abre logado, onboarding cria a pessoa uma
única vez, recarregar mantém a sessão, logout volta ao login.

### Fase 2 — Chat

- [x] Lista de conversas com agrupamento por data
- [x] Abrir conversa e carregar histórico
- [x] Enviar com streaming incremental, auto-scroll e "Parar"
- [x] Estado "acordando" após 8 s e timeout de 120 s
- [x] Erros mapeados (401/403/404/422/429/5xx/rede)
- [x] Nova conversa, atualização da lista após `done`
- [x] Abort + parcial marcada como interrompida
- [x] Testes de componente e E2E do caminho feliz

**Aceite:** conversa completa no celular token a token; parar preserva o
parcial; recarregar mostra o histórico; conversa de outra pessoa não abre
(404). Sem `dangerouslySetInnerHTML`.

### Fase 3 — PWA e acabamento

- [x] Manifest, ícones definitivos, service worker com autoUpdate
- [x] Shell offline + banner de rede + composer desabilitado
- [x] Instalação (prompt e instrução iOS)
- [x] Acessibilidade: foco, `aria-live`, teclado, contraste AA, alvos 48 px
- [x] Revisão de textos em pt-BR (sem jargão técnico)
- [ ] Matriz manual iOS/Android/desktop (exige aparelhos e deploy real)
- [ ] Rodar axe automatizado (não entrou no MVP; a checagem foi manual)

**Aceite:** instala na tela inicial, abre sem rede mostrando o shell,
stream não é cacheado, axe sem violações sérias. As duas últimas linhas da
lista são a verificação pendente.

### Fase 4 — Deploy e operação

- [ ] Projeto Pages + variáveis + domínio `app.<dominio>` (requer conta)
- [ ] `CORS_ORIGINS` exato no Render + smoke de preflight (requer deploy)
- [ ] Supabase Site URL/Redirect URLs de produção (requer painel)
- [ ] Smoke: login, onboarding, SSE, abort, reload, offline, install
- [x] Documentar rollback (redeploy de deployment anterior no Pages)
- [x] ADR 0005 registrando stack, repo único e decisão de não usar Pages
      Functions
- [x] `docs/deploy-cloudflare-pages.md` com passo a passo, smoke e
      troubleshooting
- [x] `web/README.md` e CI do front

**Aceite:** `https://app.<dominio>` funciona ponta a ponta com a API em
produção e o link mágico cai na origem certa.

---

## Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Cold start do Render (30–60 s) | primeira mensagem parece travada | estado "acordando" após 8 s, timeout 120 s, cópia honesta |
| SSE bufferizado por proxy | tokens chegam em bloco | `X-Accel-Buffering: no` já existe; testar em produção, não só local |
| Abort antes do `done` sem `conversa_id` | conversa some da lista | G1 (`event: start`) antes de liberar o chat |
| Token expirado no meio do uso | erros 401 confusos | refresh 1x + volta ao login com aviso |
| SW servir shell velho no link mágico | login falha silenciosamente | `autoUpdate`, testar `/?code=` com SW ativo, não cachear navegação autenticada |
| Conteúdo de conversa em cache | privacidade em dispositivo compartilhado | não cachear mensagens; só shell |
| XSS via resposta do LLM | execução no navegador | texto puro + CSP sem `unsafe-inline`; markdown só com sanitizer |
| `CORS_ORIGIN_REGEX` amplo | qualquer `*.pages.dev` chama a API | origem exata em produção; preview separado se necessário |
| Node 18 local | build não roda | Node 22 no `.nvmrc`, CI e Pages |
| Duplicação de mensagem em retry | histórico confuso | retry sempre como nova mensagem; nunca reenviar o mesmo POST automaticamente |
| Supabase free pausado | login/API fora | uso diário; monitorar; retenção documentada |

---

## Decisões em aberto

| Tema | Recomendação |
|---|---|
| Domínio e nome do projeto Pages | `app.<dominio>` / projeto `sera-conversa` (o subdomínio `sera.pages.dev` já está em uso) |
| Ícone/logo | decidido: monograma "S" em `public/favicon.svg`, PNGs gerados por `npm run icones` |
| Markdown nas respostas | adiar; se entrar, `react-markdown` + `rehype-sanitize` e CSP revisada |
| Cache offline de histórico | não no MVP; se pedirem, opt-in com IndexedDB + botão "limpar dados neste dispositivo" |
| Renomear/apagar conversa | Fase 4, junto de G4 |
| Editar perfil | Fase 4, junto de G3 e `PATCH` no CORS |
| Telemetria de erro | sem terceiros por padrão; se necessário, endpoint próprio no Render |

## Definição de pronto

- `web/` builda no Node 22 e no Pages sem variável faltando.
- Login, onboarding, conversa com streaming, abort e reload cobertos por
  teste automatizado (MSW) e smoke manual em produção.
- Nenhum segredo no bundle; CSP ativa; nenhum `dangerouslySetInnerHTML`.
- Service worker não intercepta API/Supabase nem guarda mensagens.
- `docs/deploy-render.md` e o ADR 0005 atualizados com as URLs finais.
