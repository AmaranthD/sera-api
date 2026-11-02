import { timingSafeEqual } from 'node:crypto'
import { createHttpApp } from 'jw-mcp/src/http-server.js'
import { captionsTool, handleCaptionsTool } from 'jw-mcp/src/tools/captions-tool.js'
import { workbookTools, handleWorkbookTools } from 'jw-mcp/src/tools/workbook-tools.js'
import { watchtowerTools, handleWatchtowerTools } from 'jw-mcp/src/tools/watchtower-tools.js'
import {
  getBibleVerseTool,
  getBibleVerseURLTool,
  getVerseWithStudyTool,
  handleScriptureTools,
  searchBibleBooksTool,
} from 'jw-mcp/src/tools/scripture-tools.js'

const ferramentas = [
  captionsTool,
  ...workbookTools,
  ...watchtowerTools,
  searchBibleBooksTool,
  getBibleVerseTool,
  getVerseWithStudyTool,
  getBibleVerseURLTool,
]

const handlers = [
  handleCaptionsTool,
  handleWorkbookTools,
  handleWatchtowerTools,
  handleScriptureTools,
]

const baseUrl = (process.env.MCP_BASE_URL || '').trim()
const authSecret = process.env.MCP_AUTH_SECRET
const apiKey = process.env.JW_API_KEY
const useAuth = process.env.MCP_AUTH !== 'false'
const port = Number(process.env.PORT || process.env.MCP_PORT || 7860)
const trustProxy =
  process.env.MCP_TRUST_PROXY === 'true' || process.env.MCP_TRUST_PROXY === '1'
const storePath = process.env.AUTH_STORE_PATH

if (!baseUrl) {
  console.error('MCP_BASE_URL é obrigatório (ex.: https://usuario-sera-jw.hf.space)')
  process.exit(1)
}
if (useAuth && !authSecret) {
  console.error('MCP_AUTH_SECRET é obrigatório quando MCP_AUTH=true')
  process.exit(1)
}
if (!apiKey) {
  console.error('JW_API_KEY é obrigatório para o facade REST')
  process.exit(1)
}

const { app, stop } = createHttpApp({
  authSecret,
  baseUrl,
  useAuth,
  storePath,
  trustProxy,
})

function chaveValida(recebida, esperada) {
  if (!esperada || typeof recebida !== 'string') return false
  if (recebida.length !== esperada.length) return false
  return timingSafeEqual(Buffer.from(recebida), Buffer.from(esperada))
}

function exigirApiKey(req, res, next) {
  if (!chaveValida(req.get('x-api-key'), apiKey)) {
    res.status(401).json({ erro: 'API key inválida' })
    return
  }
  next()
}

// O facade REST não pode virar proxy de scraping sem limite. Protege a
// chave compartilhada e evita que um bug da Sera derrube o serviço.
const LIMITE_JANELA_MS = 60_000
const LIMITE_POR_JANELA = 60
const acessosPorIp = new Map()

function limitarRequisicoes(req, res, next) {
  const agora = Date.now()
  const ip = req.ip || req.socket?.remoteAddress || 'desconhecido'
  const registro = acessosPorIp.get(ip)
  if (!registro || agora - registro.inicio >= LIMITE_JANELA_MS) {
    acessosPorIp.set(ip, { inicio: agora, total: 1 })
    next()
    return
  }
  registro.total += 1
  if (registro.total > LIMITE_POR_JANELA) {
    res.status(429).json({ erro: 'muitas requisições; tente em instantes' })
    return
  }
  next()
}

const limpezaAcessos = setInterval(() => {
  const agora = Date.now()
  for (const [ip, registro] of acessosPorIp) {
    if (agora - registro.inicio >= LIMITE_JANELA_MS) {
      acessosPorIp.delete(ip)
    }
  }
}, LIMITE_JANELA_MS)
limpezaAcessos.unref()

app.disable('x-powered-by')

app.get('/api/tools', limitarRequisicoes, exigirApiKey, (_req, res) => {
  res.json({
    ferramentas: ferramentas.map((ferramenta) => ({
      nome: ferramenta.name,
      descricao: ferramenta.description,
      parametros: ferramenta.inputSchema,
    })),
  })
})

app.post('/api/tool', limitarRequisicoes, exigirApiKey, async (req, res) => {
  const nome = req.body?.nome
  const argumentos = req.body?.argumentos

  if (typeof nome !== 'string' || !nome.trim()) {
    res.status(400).json({ erro: 'informe "nome" e "argumentos"' })
    return
  }

  const requisicao = {
    params: {
      name: nome.trim(),
      arguments:
        argumentos && typeof argumentos === 'object' ? argumentos : {},
    },
  }

  try {
    for (const handler of handlers) {
      const resultado = await handler(requisicao)
      if (resultado !== null) {
        res.json({ ferramenta: nome.trim(), resultado })
        return
      }
    }
    res.status(404).json({ erro: `ferramenta desconhecida: ${nome}` })
  } catch (erro) {
    // Detalhe fica só no log do servidor; não devolve caminho/stack para
    // quem chamou o facade.
    console.error(`Falha em ${nome}:`, erro)
    res.status(502).json({ erro: 'falha ao consultar o conteúdo JW' })
  }
})

const servidor = app.listen(port, '0.0.0.0', () => {
  console.error(`jw-mcp/sera ouvindo em 0.0.0.0:${port}`)
  console.error(`Health: ${baseUrl}/health`)
  console.error(`MCP: ${baseUrl}/mcp`)
  console.error(`Facade REST: ${baseUrl}/api/tool`)
})

function encerrar() {
  stop()
  servidor.close(() => process.exit(0))
}

process.on('SIGINT', encerrar)
process.on('SIGTERM', encerrar)
