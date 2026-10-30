import { readFile, writeFile, access } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const dist = path.join(raiz, 'dist')

function lerEnv(conteudo) {
  const valores = {}
  for (const linha of conteudo.split('\n')) {
    const limpa = linha.trim()
    if (!limpa || limpa.startsWith('#')) continue
    const separador = limpa.indexOf('=')
    if (separador === -1) continue
    const chave = limpa.slice(0, separador).trim()
    let valor = limpa.slice(separador + 1).trim()
    if (
      valor.length >= 2 &&
      valor[0] === valor[valor.length - 1] &&
      (valor[0] === '"' || valor[0] === "'")
    ) {
      valor = valor.slice(1, -1)
    }
    valores[chave] = valor
  }
  return valores
}

async function existe(caminho) {
  try {
    await access(caminho)
    return true
  } catch {
    return false
  }
}

const doArquivo = {}
for (const nome of ['.env.local', '.env']) {
  const caminho = path.join(raiz, nome)
  if (await existe(caminho)) {
    Object.assign(doArquivo, lerEnv(await readFile(caminho, 'utf8')))
  }
}

const supabase = process.env.VITE_SUPABASE_URL ?? doArquivo.VITE_SUPABASE_URL
const api = process.env.VITE_API_URL ?? doArquivo.VITE_API_URL

if (!supabase || !api) {
  console.error(
    'gerar-headers: defina VITE_SUPABASE_URL e VITE_API_URL para montar a CSP.',
  )
  process.exit(1)
}

const origem = (valor) => new URL(valor).origin
const csp = [
  "default-src 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "img-src 'self' data:",
  "font-src 'self'",
  "style-src 'self'",
  "script-src 'self'",
  "manifest-src 'self'",
  "worker-src 'self'",
  `connect-src 'self' ${origem(supabase)} ${origem(api)}`,
].join('; ')

const headers = `/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: no-referrer
  Permissions-Policy: geolocation=(), microphone=(), camera=()
  Content-Security-Policy: ${csp}

/assets/*
  Cache-Control: public, max-age=31536000, immutable

/index.html
  Cache-Control: no-cache

/manifest.webmanifest
  Cache-Control: no-cache

/sw.js
  Cache-Control: no-cache
`

await writeFile(path.join(dist, '_headers'), headers, 'utf8')
console.log('gerado dist/_headers')
