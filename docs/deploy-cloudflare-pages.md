# Deploy — PWA no Cloudflare Pages

Status em 2026-10-29: front implementado em `web/`, build e testes verdes em
Node 22. O projeto no Cloudflare Pages ainda **não** foi criado; este
documento é o passo a passo para publicar e validar.

O desenho completo está em `docs/planejamento-front.md` e a decisão de
arquitetura em `docs/adr/0005-front-react-pages.md`.

> **Deploy atual:** o Cloudflare pode oferecer o fluxo novo de **Workers com
> assets estáticos** em vez de Pages. Se você já tem uma URL
> `https://<worker>.<account>.workers.dev` ou caiu no build que roda
> `pip install .`, siga `docs/deploy-cloudflare-workers.md`. Os dois caminhos
> publicam o mesmo `web/dist`.
>
> **Já criou um Worker que está servindo `web/` cru?** Crie o projeto Pages
> primeiro, valide a URL nova e só então apague o Worker em
> **Settings → Delete**. Assim você não fica sem nenhum endereço no meio do
> caminho.

## Visão geral

| Peça | Onde fica |
|---|---|
| Shell, login Supabase Auth, SSE | Cloudflare Pages (estático) |
| API FastAPI, JWT, PostgREST | Render |
| Auth e banco com RLS | Supabase |

O navegador fala **direto** com o Render. Não há Pages Functions, proxy nem
`service_role` no front. A única chave pública é a `anon/publishable` do
Supabase.

## 1. Pré-requisitos

- Conta no Cloudflare com Pages habilitado.
- Projeto Supabase `zcvnfxelcgcydopcdayc` (ou o seu) com Auth por e-mail
  configurado — ver `docs/deploy-render.md`.
- API publicada no Render respondendo em `/health`.
- Repositório com a pasta `web/` no branch que o Pages vai acompanhar.

## 2. Criar o projeto no Pages

1. Cloudflare Dashboard → **Workers & Pages → Create → Pages → Connect to
   Git**.
2. Autorize o GitHub e escolha `AmaranthD/sera-api`.
3. Configure:

| Campo | Valor |
|---|---|
| Project name | `sera-conversa` (o subdomínio é único; `sera.pages.dev` já está em uso) |
| Production branch | `main` |
| Framework preset | `None` (ou `Vite`) |
| Root directory | `web` |
| Build command | `npm ci && npm run build` |
| Build output directory | `dist` |
| Node version | `22` (variável `NODE_VERSION=22` ou `web/.nvmrc`) |

O **Project name** define a URL `https://<nome>.pages.dev`. Ele é único no
mundo inteiro: `sera`, `sera-web` e `sera-ai` já estão ocupados. Se o nome
desejado não estiver disponível, escolha outro (ex.: `sera-conversa`,
`sera-familia`, `sera-assistente`) ou use um domínio próprio.

4. Em **Environment variables**, adicione somente variáveis públicas:

```
VITE_SUPABASE_URL=https://zcvnfxelcgcydopcdayc.supabase.co
VITE_SUPABASE_ANON_KEY=<publishable/anon key>
VITE_API_URL=https://sera-api.onrender.com
```

> **Nunca** coloque `service_role`, `DATABASE_URL`, `LLM_API_KEY` ou senha do
> banco no Pages. Tudo em `VITE_*` vai para o bundle e é legível por qualquer
> visitante. A `anon/publishable` é pública por desenho e depende do RLS.

5. Salve e faça o primeiro deploy.

O build executa `scripts/gerar-headers.mjs`, que gera `dist/_headers` com CSP
montada a partir de `VITE_SUPABASE_URL` e `VITE_API_URL`. Se faltar qualquer
uma, o build falha de propósito.

### Deploy manual (fallback)

Útil para testar um build local antes de configurar o Git:

```bash
cd web
npm ci
VITE_SUPABASE_URL=https://zcvnfxelcgcydopcdayc.supabase.co \
VITE_SUPABASE_ANON_KEY=<anon> \
VITE_API_URL=https://sera-api.onrender.com \
  npm run build
npx wrangler pages deploy dist --project-name sera
```

## 3. Conectar as origens

### Supabase

Authentication → URL Configuration:

- **Site URL:** `https://<projeto>.pages.dev` (ou `https://app.<dominio>`).
- **Redirect URLs:** inclua a origem de produção **e** os previews que forem
  testar login de verdade:
  - `https://<projeto>.pages.dev/**`
  - `https://app.<dominio>/**`
  - `https://<hash>.<projeto>.pages.dev/**` (só se previews forem usados)

O front manda `emailRedirectTo` com `window.location.origin`, então o link
volta para a mesma origem em que a pessoa pediu o acesso.

### Render

No dashboard do Render, ajuste `CORS_ORIGINS` para a origem exata:

```
CORS_ORIGINS=https://<projeto>.pages.dev
```

Ao usar domínio próprio, troque para `https://app.<dominio>`. O regex de
`*.pages.dev` já existe para previews, mas produção deve usar origem exata.

### Domínio próprio (opcional)

1. Pages → Custom domains → adicione `app.<dominio>` e crie o CNAME pedido.
2. Atualize `CORS_ORIGINS` no Render.
3. Atualize Site URL / Redirect URLs no Supabase.
4. Rebuild do Pages (as `VITE_*` só mudam se a API mudar de host).

## 4. Smoke test de produção

Faça em uma janela anônima e, depois, no celular:

- [ ] `https://<origem>/` abre o login.
- [ ] O e-mail com link/código chega e entra.
- [ ] O onboarding cria nome, faixa etária e perfil uma única vez.
- [ ] Recarregar a página mantém a sessão.
- [ ] Enviar mensagem mostra tokens chegando (não tudo de uma vez).
- [ ] "Parar" encerra o stream e marca a parcial como interrompida.
- [ ] Recarregar a conversa mostra o histórico.
- [ ] A lista lateral mostra o título vindo da primeira mensagem.
- [ ] Outra conta não abre a conversa (404).
- [ ] Abrir offline mostra o shell e o aviso de sem conexão.
- [ ] O navegador oferece "Instalar app" (Android/desktop) e o iOS mostra a
      instrução de Compartilhar → Adicionar à Tela de Início.
- [ ] DevTools → Application → Service Workers: o SW está ativo e o Cache
      Storage **não** contém respostas de `/chat`, `/conversas` nem do
      Supabase.

Teste o cold start do Render: a primeira mensagem depois de ~15 min parados
pode levar 30–60 s. Após 8 s o app mostra "A Sera está acordando".

## 5. Rollback

Pages → Deployments → escolha o deployment anterior → **Rollback**. O
rollback troca apenas o shell estático; API e banco não são afetados.

Se o problema vier de uma variável de build errada, corrija a variável e
dispare **Retry deployment** no deployment desejado.

## 6. Problemas comuns

| Sintoma | Causa provável | Correção |
|---|---|---|
| Tela "Falta configurar o app" | `VITE_*` ausente no build | Preencha as três variáveis e refaça o deploy |
| Link mágico cai em `localhost` | Site URL/Redirect URLs errados no Supabase | Corrija em Authentication → URL Configuration |
| `401` logo após entrar | `anon key` de outro projeto | Confira `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` |
| Requisição bloqueada pela CSP | host da API/Supabase diferente do build | Confira `VITE_API_URL`/`VITE_SUPABASE_URL` e refaça o build |
| CORS no `/chat` | origem do Pages fora de `CORS_ORIGINS` | Atualize no Render e redeploy |
| Shell antigo após deploy | SW servindo cache anterior | O app mostra "nova versão"; recarregue. Em último caso, limpe o site data |
| Login falha só com SW ativo | shell velho perdeu o `?code=` | O SW usa `autoUpdate` e não cacheia `/chat`; limpe o cache e tente de novo |

## 7. Segurança

- CSP gerada no pós-build: `script-src 'self'`, sem `unsafe-inline`;
  `connect-src` limitado a Supabase + API.
- `frame-ancestors 'none'`, `nosniff`, `Referrer-Policy: no-referrer`.
- Respostas da Sera são renderizadas como texto puro (`white-space:
  pre-wrap`), nunca com `dangerouslySetInnerHTML`.
- O service worker precacheia apenas o shell; conteúdo de conversa não é
  gravado no dispositivo.
- Qualquer serviço novo (ex.: telemetria) exige atualizar a CSP em
  `web/scripts/gerar-headers.mjs`.
