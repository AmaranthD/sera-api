# Deploy — Worker com assets estáticos (alternativa ao Pages)

O dashboard novo do Cloudflare pode oferecer **Workers** em vez de **Pages**
ao conectar um repositório. Para um site estático isso funciona igual: o
Worker serve os arquivos do build e aceita `_headers` e `_redirects`.

Este documento cobre o caminho **Workers**. O caminho Pages continua em
`docs/deploy-cloudflare-pages.md`.

## O erro comum

Se o log do build mostra algo assim:

```
Installing project dependencies: pip install .
...
Output Directory: web
Read 108 files from the assets directory .../web
Uploaded sera
https://sera.<account>.workers.dev
```

O Cloudflare **não buildou o front**. Ele detectou o `pyproject.toml` da API,
rodou `pip install .` e publicou a pasta `web/` (código-fonte) como se fosse
o site pronto. O resultado é uma página quebrada ou em branco.

O correto é:

1. rodar `npm ci && npm run build` dentro de `web/`;
2. publicar `web/dist`, que contém o HTML/CSS/JS compilados, o manifest e o
   service worker;
3. deixar o `wrangler.jsonc` da raiz apontar para `./web/dist`.

## 1. Configuração no repositório

O arquivo `wrangler.jsonc` na raiz já faz isso:

```jsonc
{
  "name": "sera",
  "compatibility_date": "2026-10-30",
  "observability": { "enabled": true },
  "assets": {
    "directory": "./web/dist",
    "not_found_handling": "single-page-application"
  }
}
```

- `name` precisa ser o mesmo nome do Worker no Cloudflare (hoje `sera`).
- `not_found_handling: "single-page-application"` faz as rotas `/c/...`
  caírem no `index.html`, sem 404 ao recarregar.
- `_headers` (CSP) e `_redirects` são lidos de dentro de `web/dist`; o build
  já coloca os dois lá.

Se o Worker tiver outro nome, troque `name` no arquivo **e** no painel. O
endereço muda junto: `https://<nome>.<account>.workers.dev`.

## 2. Configuração no painel

No Cloudflare:

1. **Workers & Pages** → Worker **sera**.
2. **Settings → Build**.
3. Em **Build Configuration**, preencha:

| Campo | Valor |
|---|---|
| Git branch | `main` |
| Root directory | `/` (raiz do repositório) |
| Build command | `cd web && npm ci && npm run build` |
| Deploy command | `npx wrangler deploy` |
| Preview command | deixe o padrão (`npx wrangler preview`) |

4. Em **Build variables and secrets** (não em “Variables & Secrets”, que é
   runtime), adicione:

```
VITE_SUPABASE_URL=https://zcvnfxelcgcydopcdayc.supabase.co
VITE_SUPABASE_ANON_KEY=<anon/publishable key>
VITE_API_URL=https://sera-api.onrender.com
NODE_VERSION=22
```

> As `VITE_*` precisam existir **no build**. Se você colocá-las apenas nas
> variáveis de runtime, o Vite não as vê e o app cai na tela “Falta
> configurar o app”.

5. Salve e clique em **Deploy** / **Retry deployment**.

## 3. Como saber se funcionou

O log deve conter:

```
vite v8...
✓ built in ...
PWA v2.0.0
files generated
  dist/sw.js
gerado dist/_headers
...
Uploaded sera
https://sera.<account>.workers.dev
```

E **não** deve conter `pip install .` nem `Read ... files from .../web`
(nesse caso ele ainda está publicando o código-fonte).

Abra a URL do Worker. Deve aparecer a tela de login da Sera.

Testes rápidos:

```bash
curl -I https://sera.<account>.workers.dev/
# 200 + content-security-policy

curl -s -o /dev/null -w "%{http_code}\n" https://sera.<account>.workers.dev/c/teste
# 200 (SPA)
```

## 4. Ligar Supabase e Render

Use a URL real do Worker:

### Supabase → Authentication → URL Configuration

```
Site URL:
https://sera.<account>.workers.dev

Redirect URLs:
https://sera.<account>.workers.dev/**
http://localhost:5173/**
```

### Render → sera-api → Environment

```
CORS_ORIGINS=https://sera.<account>.workers.dev
```

Sem barra no final. Salve e espere o Render reiniciar.

## 5. Domínio próprio

Worker → **Settings → Domains & Routes → Add custom domain**. Informe
`app.<dominio>` e crie o CNAME indicado.

Depois atualize:

- Supabase: Site URL e Redirect URLs com `https://app.<dominio>`;
- Render: `CORS_ORIGINS=https://app.<dominio>`.

As `VITE_*` continuam iguais; só rebuilda se a API ou o Supabase mudarem de
host.

## 6. Rollback

Worker → **Deployments** → escolha a versão anterior → **Deploy** / **Rollback**.
Isso troca só os assets; API e banco não são afetados.

## 7. Pages ou Workers?

| | Pages | Workers static assets |
|---|---|---|
| URL | `<projeto>.pages.dev` (único) | `<worker>.<account>.workers.dev` |
| Build | build command + output dir | build command + `wrangler.jsonc` |
| `_headers` / `_redirects` | sim | sim |
| SPA fallback | `_redirects` | `not_found_handling` |
| Uso neste projeto | documentado | **usado no deploy atual** |

Os dois servem o mesmo `web/dist`. Se um dia quiser migrar para Pages, o
`wrangler.jsonc` não atrapalha: basta criar o projeto Pages com root `web`,
build `npm ci && npm run build` e output `dist`.

## 8. Apagar um Worker antigo

Só faça isso depois que a URL nova (Pages ou outro Worker) estiver
funcionando.

1. **Workers & Pages** → Worker antigo.
2. **Settings** → role até o fim.
3. **Delete** / **Delete Worker**.
4. Digite o nome do Worker para confirmar.

Se houver um domínio personalizado apontando para ele, remova o domínio
antes. A URL `https://<worker>.<account>.workers.dev` deixa de responder
assim que o Worker é apagado.
