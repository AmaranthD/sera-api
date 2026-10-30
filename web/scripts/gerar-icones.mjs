import { mkdir, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import sharp from 'sharp'

const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const destino = path.join(raiz, 'public', 'icons')
await mkdir(destino, { recursive: true })

const svg = await readFile(path.join(raiz, 'public', 'favicon.svg'), 'utf8')

async function gerar(nome, tamanho, { mascara = false } = {}) {
  let entrada = svg
  if (mascara) {
    entrada = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
      <rect width="512" height="512" fill="#1e4b3d"/>
      <text x="256" y="332" text-anchor="middle"
        font-family="Georgia, 'Iowan Old Style', 'Palatino Linotype', 'DejaVu Serif', serif"
        font-size="250" fill="#faf7ee">S</text>
    </svg>`
  }
  await sharp(Buffer.from(entrada))
    .resize(tamanho, tamanho)
    .png({ compressionLevel: 9 })
    .toFile(path.join(destino, nome))
  console.log(`gerado ${nome} (${tamanho}x${tamanho})`)
}

await gerar('icon-192.png', 192)
await gerar('icon-512.png', 512)
await gerar('icon-maskable-512.png', 512, { mascara: true })
await gerar('apple-touch-icon.png', 180)
