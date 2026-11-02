# Sera — front (PWA)

Interface da Sera: React 19 + TypeScript + Vite, publicada como estático no
Cloudflare Pages e conectada direto à API no Render. O desenho e as decisões
estão em `../docs/planejamento-front.md` e
`../docs/adr/0005-front-react-pages.md`.

## Requisitos

- Node 22 (há um `.nvmrc`; o Node 18 não roda o Vite atual).
- npm 10+.

```bash
cd web
nvm use            # ou: nvm install 22
npm ci
cp .env.example .env.local
```

Preencha `web/.env.local`:

```
VITE_SUPABASE_URL=https://<ref>.supabase.co
VITE_SUPABASE_ANON_KEY=<publishable/anon key>
VITE_API_URL=https://<api>.onrender.com
```

São variáveis **públicas** de build. Nunca coloque `service_role`,
`LLM_API_KEY` ou senha do banco aqui: tudo em `VITE_*` vai para o bundle.

## Scripts

| Comando              | O que faz                                             |
| -------------------- | ----------------------------------------------------- |
| `npm run dev`        | Vite em `http://localhost:5173`                       |
| `npm run build`      | `tsc --noEmit` + build + gera `dist/_headers` com CSP |
| `npm run preview`    | Serve o `dist/` localmente                            |
| `npm run lint`       | ESLint                                                |
| `npm run typecheck`  | TypeScript sem emitir                                 |
| `npm test`           | Vitest (unitários + componentes)                      |
| `npm run test:watch` | Vitest em watch                                       |
| `npm run e2e`        | Playwright (Chromium)                                 |
| `npm run format`     | Prettier                                              |
| `npm run icones`     | Regenera os PNGs a partir de `public/favicon.svg`     |

O build falha de propósito se `VITE_SUPABASE_URL` ou `VITE_API_URL` faltarem,
porque a CSP depende delas.

## Estrutura

```
src/
├── main.tsx                 # valida env e monta o app
├── App.tsx                  # rotas e providers
├── env.ts                   # VITE_* tipadas e validadas
├── api/
│   ├── http.ts              # fetch + Bearer + timeout + refresh 1x em 401
│   ├── erros.ts             # ErroApi e traduções em pt-BR
│   ├── sse.ts               # parser SSE puro (sem React)
│   ├── chat.ts              # POST /chat e conversão dos eventos
│   └── sera.ts              # pessoas, conversas, mensagens, saúde
├── auth/                    # supabase-js, sessão e OTP
├── pessoa/                  # carrega/cria a pessoa do onboarding
├── chat/                    # ChatProvider: stream, abort, URL da conversa
├── dominios/                # tipos e funções puras (texto, datas, grupos)
├── componentes/             # Botão, Campo, Banner, Marca, ícones…
├── telas/
│   ├── login/
│   ├── onboarding/
│   ├── chat/                # shell, lista, drawer, mensagens, composer
│   └── conta/
├── pwa/                     # online/offline e instalação
├── voz/                     # Web Speech API (falar respostas e ditar)
└── estilos/global.css       # tokens, reset e utilidades
```

Regra de dependência: `telas → contexto/providers → api`; nada em `api/`
importa React. O parser SSE e as funções de domínio são testáveis sem
navegador.

## Voz

- **Modo de voz**: o botão no cabeçalho alterna `desligado` → `voz on`
  (lê cada resposta automaticamente) → `só áudio` (lê e esconde o texto, com
  botão "Mostrar texto"). A escolha fica no `localStorage`.
- **Ouvir resposta**: cada resposta da Sera tem um botão que lê o texto com
  `speechSynthesis`, preferindo voz pt-BR local (Francisca, Thalita etc.).
- **Ditar mensagem**: o microfone do Composer usa `SpeechRecognition`
  (`webkitSpeechRecognition` no Safari). O texto é anexado ao rascunho e você
  revisa antes de enviar.
- O reconhecimento pode enviar o áudio para o serviço do navegador; por isso
  o app pede consentimento uma vez e não grava nem guarda áudio.
- Onde a API não existe (Firefox, por exemplo), os botões somem e o chat
  continua normal. Nenhum backend ou chave nova é necessário.

## Contrato do chat

`POST /chat` responde `text/event-stream`:

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

O `start` permite atualizar a URL e a lista mesmo se a conexão cair antes do
`done`. Interromper usa `AbortController`; o backend grava a parcial como
`interrompida`.

## Testes

- **Vitest + Testing Library + MSW**: parser SSE (chunks partidos, CRLF,
  UTF-8 no meio de acento, evento sem `done`), HTTP (Bearer, refresh 401,
  timeout, 422), contrato do chat, agrupamento de conversas, Composer e
  mensagens.
- **Playwright**: sessão Supabase falsa em `localStorage` e `page.route`
  simulando Supabase + API. Cobre abrir o app, enviar com Enter, atualizar a
  URL, abrir histórico, a tela de conta e o shell offline (build + preview
  com service worker). Nenhum pedido sai para a rede.

```bash
npx playwright install chromium   # uma vez
npm run e2e
```

O E2E roda `npm run build` + `npm run preview` na porta 4317 (configurado em
`playwright.config.ts`), para exercitar o service worker de verdade.

## PWA

- `vite-plugin-pwa` com `registerType: 'autoUpdate'`.
- Tema claro/escuro automático pelo sistema (`prefers-color-scheme`):
  branco + indigo no claro, preto + indigo no escuro. O manifest usa indigo.
- Precache só do shell; `/chat`, Supabase e `/health` ficam fora do service
  worker.
- Offline: o shell abre, aparece o banner "sem conexão" e o composer fica
  desabilitado. Nenhuma mensagem é gravada no dispositivo; só o perfil mínimo
  (nome/faixa/perfil) fica em `localStorage`, por usuário, para o shell
  abrir sem rede. O cache é limpo no logout e em 401.
- Instalação: prompt nativo quando disponível; no iOS, instrução
  Compartilhar → Adicionar à Tela de Início.

## Deploy

Passo a passo em `../docs/deploy-cloudflare-pages.md` (Pages) ou
`../docs/deploy-cloudflare-workers.md` (Workers com assets estáticos — é o
fluxo usado hoje). Resumo:

- build `npm ci && npm run build` dentro de `web/`;
- publicar `web/dist`;
- Node 22;
- variáveis de **build** `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`,
  `VITE_API_URL` (e `NODE_VERSION=22`).

Para Workers, crie um `wrangler.jsonc` na raiz apontando para `./web/dist` e
ativando o fallback de SPA (não use esse arquivo no fluxo Pages).

CI em `.github/workflows/web.yml` roda lint, format, typecheck, testes, build
e Playwright em Node 22.
