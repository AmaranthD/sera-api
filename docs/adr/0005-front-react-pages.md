# Front React + Vite em `web/`, falando direto com a API

## Status

accepted (2026-10-29)

## Contexto

A API já está no Render com JWT do Supabase, PostgREST e RLS
(`docs/adr/0004-deploy-cloudflare-render-supabase.md`). Falta a interface: um
PWA instalável, mobile-first, em português, usável por pessoas da família sem
instrução técnica.

O plano original de deploy previa Cloudflare Pages com Pages Functions como
proxy. Isso adicionaria latência, outro runtime e um lugar a mais para
depurar, sem ganho de segurança: a API já valida o JWT e o RLS é a barreira
final.

## Decisão

1. **SPA React + TypeScript + Vite** em `web/`, no mesmo repositório da API,
   publicada como estático no Cloudflare Pages.
2. **Sem Pages Functions e sem proxy.** O navegador chama
   `https://sera-api.onrender.com` com `Authorization: Bearer
   <access_token>`. A origem exata entra em `CORS_ORIGINS`.
3. **supabase-js só para Auth.** Login por OTP (link mágico + código),
   sessão em `localStorage`, `flowType: 'pkce'` e `autoRefreshToken`. O banco
   continua exclusivamente atrás da API.
4. **CSS Modules + tokens** em `src/estilos/global.css`, sem UI kit e sem
   Tailwind. Ícones SVG inline e fontes do sistema.
5. **Estado explícito, sem TanStack Query.** `api/http.ts` cuida de Bearer,
   timeout e refresh 1x em 401; `api/sse.ts` é o parser puro; o
   `ChatProvider` mantém a máquina de estados do envio e o `AbortController`.
6. **`vite-plugin-pwa`** com `autoUpdate`, precache apenas do shell e
   `navigateFallback` para `/index.html`. Nenhuma resposta de conversa é
   cacheada.
7. **CSP gerada no pós-build** por `web/scripts/gerar-headers.mjs`, a partir
   de `VITE_SUPABASE_URL` e `VITE_API_URL`. Não existe `_headers` estático
   para não versionar hosts de produção.
8. **Contrato do SSE ganhou `event: start`** com `conversa_id` e
   `mensagem_id` antes dos tokens (G1) e **título da conversa derivado da
   primeira mensagem** no backend (G2). Ambos com teste em
   `tests/api/test_chat.py`.

## Consequências

- Deploy do front independente do backend: rollback no Pages troca só o
  shell.
- Nenhum segredo no bundle; a `anon/publishable` é pública e o RLS limita o
  alcance.
- CSP mais restritiva (`script-src 'self'`, sem `unsafe-inline`) porque não
  há injeção de runtime no HTML.
- Previews do Pages só funcionam com login se a URL de preview estiver nas
  Redirect URLs do Supabase; para previews com dados reais, o ideal é um
  projeto Pages separado com allowlist de CORS estreita.
- Sem SSR: o primeiro paint depende do JS. Aceitável para um app de conversa
  autenticado, que já precisa de rede para qualquer conteúdo.
- O service worker não guarda histórico; abrir offline mostra o shell e
  desabilita o composer. O perfil mínimo (nome/faixa/perfil) fica em
  `localStorage` por usuário para o shell abrir sem rede; conversas e
  mensagens não são cacheadas. Se um dia houver cache de conversa, será
  opt-in e com botão de limpar.

## Alternativas descartadas

- **Pages Functions como proxy:** latência extra, mais um runtime e nenhuma
  proteção adicional — a API já valida o JWT.
- **Next.js/Remix com SSR:** o conteúdo é autenticado e dinâmico; SSR só
  adicionaria complexidade de deploy sem melhorar o primeiro uso.
- **UI kit/Tailwind:** o app tem poucas telas e precisa de controle fino de
  contraste, alvos de toque e tipografia; CSS Modules resolve com menos
  dependências.
- **EventSource:** não faz `POST` nem envia `Authorization`; o parser próprio
  sobre `fetch` + `ReadableStream` é necessário para o contrato atual.
- **Cache offline de mensagens:** privacidade em dispositivo compartilhado;
  fora do MVP.
- **Chamar PostgREST direto do front:** duplicaria regras de negócio e
  espalharia o contrato; a API continua sendo a única porta.
