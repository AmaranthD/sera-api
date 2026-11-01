---
title: Sera JW MCP
emoji: 📖
colorFrom: indigo
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# Sera JW MCP

Serviço separado que expõe o [`jw-mcp`](https://github.com/advenimus/jw-mcp)
(MIT) de duas formas:

1. **MCP Streamable HTTP** em `/mcp`, com OAuth — para Claude, Grok, ChatGPT
   e qualquer cliente MCP.
2. **Facade REST** em `/api/tool`, protegida por `X-API-Key` — para a Sera
   chamar pelo backend Python.

O mesmo container serve as duas.

## Variáveis obrigatórias

| Variável | Para que serve |
|---|---|
| `MCP_BASE_URL` | URL pública exata, sem `/mcp` e sem barra no fim. Ex.: `https://usuario-sera-jw.hf.space` |
| `MCP_AUTH_SECRET` | Chave que a pessoa digita na tela de login do conector MCP. Mínimo 16 caracteres |
| `JW_API_KEY` | Chave do facade REST que a Sera usa no header `X-API-Key` |
| `MCP_TRUST_PROXY` | `true` atrás de Hugging Face/Koyeb/Render |
| `MCP_AUTH` | `true` em produção |
| `AUTH_STORE_PATH` | `/tmp/jw-mcp-auth.json` em disco efêmero |

Gere as chaves com:

```bash
openssl rand -hex 32
```

## Opção 1 — Hugging Face Space (grátis quando disponível)

> Em 2026 o Docker Space pode exigir plano pago dependendo da conta. Se for
> o caso, use a opção 3 (Render), que já vem no `render.yaml` do repositório.

1. Crie um **Space** novo em [huggingface.co/new-space](https://huggingface.co/new-space):
   - SDK: **Docker**
   - Template: **Blank**
   - Hardware: **CPU basic (free)**
2. Clone o repositório do Space e copie o conteúdo desta pasta (`jw-mcp/`)
   para a raiz dele, **sem** `node_modules` (o Docker builda).
   ```bash
   git clone https://huggingface.co/spaces/<usuario>/<space>
   cp -r jw-mcp/* jw-mcp/.dockerignore <space>/
   ```
   O `README.md` desta pasta já tem o cabeçalho YAML que o Space precisa.
3. Em **Settings → Variables and secrets**, defina:
   - `MCP_BASE_URL` = `https://<usuario>-<space>.hf.space`
   - `MCP_AUTH_SECRET` (secret)
   - `JW_API_KEY` (secret)
   - `MCP_TRUST_PROXY` = `true`
   - `MCP_AUTH` = `true`
   - `AUTH_STORE_PATH` = `/tmp/jw-mcp-auth.json`
4. Faça commit/push e espere o build.
5. Teste:
   ```bash
   curl https://<usuario>-<space>.hf.space/health
   # {"status":"ok"}
   ```
6. Conector MCP: use `https://<usuario>-<space>.hf.space/mcp`. Na tela de
   login, digite a `MCP_AUTH_SECRET`.
7. Facade REST:
   ```bash
   curl -X POST https://<usuario>-<space>.hf.space/api/tool \
     -H "X-API-Key: $JW_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"nome":"search_bible_books","argumentos":{"query":"matthew"}}'
   ```

## Opção 2 — Koyeb free

1. Crie um **Web Service** a partir do repositório `AmaranthD/sera-api`.
2. Build: **Dockerfile**, caminho `jw-mcp/Dockerfile`, contexto `jw-mcp`.
3. Porta: `7860` (ou deixe o Koyeb usar `$PORT`; o `start.js` respeita).
4. Instância: free / scale-to-zero.
5. Variáveis:
   - `MCP_BASE_URL` = `https://<servico>.koyeb.app`
   - `MCP_AUTH_SECRET`, `JW_API_KEY`, `MCP_TRUST_PROXY=true`,
     `MCP_AUTH=true`, `AUTH_STORE_PATH=/tmp/jw-mcp-auth.json`
6. Health check: `/health`.

## Opção 3 — Render free (junto da Sera)

O `render.yaml` do repositório já declara o `sera-jw`. Passo a passo em
`docs/deploy-render.md` (seção "Serviço JW"). Resumo:

1. Build: `jw-mcp/Dockerfile`, contexto `jw-mcp`, health `/health`.
2. Variáveis: `MCP_BASE_URL` (URL final, sem `/mcp`),
   `MCP_AUTH_SECRET`, `JW_API_KEY`, `MCP_TRUST_PROXY=true`,
   `MCP_AUTH=true`, `AUTH_STORE_PATH=/tmp/jw-mcp-auth.json`.
3. No `sera-api`, aponte `JW_API_URL=https://<sera-jw>.onrender.com/api` e
   repita o `JW_API_KEY`.
4. Os dois serviços free dividem 750 h/mês e dormem após 15 min sem tráfego.

## Ligar na Sera (Render)

No serviço `sera-api`, em **Environment**, adicione:
```env
JW_API_URL=https://<seu-servico-jw>/api
JW_API_KEY=<a mesma JW_API_KEY>
JW_TIMEOUT=90
JW_MAX_RODADAS=2
```

A Sera expõe uma ferramenta `jw` que chama esse facade. Enquanto
`JW_API_URL`/`JW_API_KEY` não estiverem definidos, a ferramenta fica
desligada e o chat continua normal.

## Teste local

```bash
cd jw-mcp
npm install
MCP_BASE_URL=http://127.0.0.1:7860 \
MCP_AUTH=false \
JW_API_KEY=teste \
npm start

curl http://127.0.0.1:7860/health
curl -X POST http://127.0.0.1:7860/api/tool \
  -H 'X-API-Key: teste' \
  -H 'Content-Type: application/json' \
  -d '{"nome":"search_bible_books","argumentos":{"query":"matthew"}}'
```

`MCP_AUTH=false` só é aceito em `localhost`/`127.0.0.1`.

## Ferramentas expostas

- Bíblia: `search_bible_books`, `get_bible_verse`,
  `get_verse_with_study`, `get_bible_verse_url`
- Apostila: `getWorkbookLinks` → `getWorkbookContent`
- A Sentinela: `getWatchtowerLinks` → `getWatchtowerContent`
- Vídeos: `get_jw_captions`

## Limitações do grátis

- O Space/serviço **dorme** por inatividade. O primeiro acesso pode levar
  ~1 minuto. Um ping em `/health` antes de usar ajuda.
- O disco é efêmero: tokens OAuth em `/tmp` somem em restart/deploy. No
  conector MCP, é só entrar de novo com a `MCP_AUTH_SECRET`.
- O Space é público, mas as rotas são protegidas por OAuth/API key.
- Conteúdo do JW.org continua sujeito aos termos do site; este serviço é
  para uso pessoal/estudo.
