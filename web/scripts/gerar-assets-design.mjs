import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import sharp from 'sharp'

const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const fontes = path.resolve(raiz, '..', 'imgs')
const publico = path.join(raiz, 'public')

const LOGO = path.join(fontes, 'logo', 'Gemini_Generated_Image_4t76fq4t76fq4t76.jpeg')
const OP = path.join(fontes, 'op', 'Gemini_Generated_Image_p2fvhip2fvhip2fv.jpeg')

const OURO = '#d8ad5c'
const NOITE = '#0b1020'
const BORDA = 8

function svgBorda(tamanho) {
  const metade = BORDA / 2
  return Buffer.from(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${tamanho}" height="${tamanho}">
      <rect x="${metade}" y="${metade}" width="${tamanho - BORDA}" height="${tamanho - BORDA}"
        fill="none" stroke="${OURO}" stroke-width="${BORDA}" />
    </svg>`,
  )
}

await mkdir(path.join(publico, 'icons'), { recursive: true })
await mkdir(path.join(publico, 'fundo'), { recursive: true })

// Marca principal: o elmo em close, quadrado, para usar como medalhão.
await sharp(LOGO)
  .resize(512, 512, { fit: 'cover' })
  .webp({ quality: 88 })
  .toFile(path.join(publico, 'marca-sera.webp'))

// Ilustração da paladina para o login / estados vazios.
await sharp(OP)
  .resize({ width: 900, withoutEnlargement: true })
  .webp({ quality: 84 })
  .toFile(path.join(publico, 'paladina.webp'))

// Ícones do PWA: quadrado do elmo com moldura dourada.
for (const [nome, tamanho] of [
  ['icon-192-v2.png', 192],
  ['icon-512-v2.png', 512],
  ['apple-touch-icon-v2.png', 180],
]) {
  const base = await sharp(LOGO)
    .resize(tamanho, tamanho, { fit: 'cover' })
    .png()
    .toBuffer()
  await sharp(base)
    .composite([{ input: svgBorda(tamanho) }])
    .png({ compressionLevel: 9, palette: true })
    .toFile(path.join(publico, 'icons', nome))
}

// Maskable: elmo menor, centralizado em um campo noturno com anel dourado.
const maskTamanho = 512
const logoMask = await sharp(LOGO).resize(360, 360, { fit: 'cover' }).png().toBuffer()
const anel = Buffer.from(
  `<svg xmlns="http://www.w3.org/2000/svg" width="${maskTamanho}" height="${maskTamanho}">
    <circle cx="256" cy="256" r="196" fill="none" stroke="${OURO}" stroke-width="8" />
  </svg>`,
)
await sharp({
  create: {
    width: maskTamanho,
    height: maskTamanho,
    channels: 4,
    background: NOITE,
  },
})
  .composite([
    { input: logoMask, left: 76, top: 76 },
    { input: anel, left: 0, top: 0 },
  ])
  .png({ compressionLevel: 9, palette: true })
  .toFile(path.join(publico, 'icons', 'icon-maskable-512-v2.png'))

console.log('assets de design gerados em web/public')
