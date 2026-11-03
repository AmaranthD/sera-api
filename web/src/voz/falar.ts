let vozes: SpeechSynthesisVoice[] = []
let geracao = 0
let audioAtual: HTMLAudioElement | null = null
let urlAudio: string | null = null

export class FalaCancelada extends Error {
  constructor() {
    super('fala cancelada')
    this.name = 'FalaCancelada'
  }
}

export interface EstadoFala {
  id: string | null
  falando: boolean
}

const inscritos = new Set<(estado: EstadoFala) => void>()

function avisar(estado: EstadoFala): void {
  for (const ouvinte of inscritos) ouvinte(estado)
}

export function assinarFala(
  ouvinte: (estado: EstadoFala) => void,
): () => void {
  inscritos.add(ouvinte)
  return () => inscritos.delete(ouvinte)
}

function sintese(): SpeechSynthesis | null {
  if (typeof window === 'undefined') return null
  return 'speechSynthesis' in window ? window.speechSynthesis : null
}

export function falaSuportada(): boolean {
  return sintese() !== null && typeof SpeechSynthesisUtterance !== 'undefined'
}

function carregarVozes(): SpeechSynthesisVoice[] {
  const motor = sintese()
  if (!motor) return []
  vozes = motor.getVoices()
  return vozes
}

function vozPtBr(): SpeechSynthesisVoice | null {
  const lista = vozes.length > 0 ? vozes : carregarVozes()
  const ptBr = lista.filter((voz) => voz.lang.toLowerCase().startsWith('pt-br'))
  const feminina = ptBr.filter((voz) =>
    /francisca|thalita|maria|luciana|female|feminin/i.test(voz.name),
  )
  return (
    feminina.find((voz) => voz.localService) ??
    feminina[0] ??
    ptBr.find((voz) => voz.localService) ??
    ptBr[0] ??
    null
  )
}

if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
  window.speechSynthesis.addEventListener('voiceschanged', () => {
    carregarVozes()
  })
}

/** Remove marcação que atrapalha a leitura em voz alta. */
export function textoParaFala(texto: string): string {
  return texto
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`[^`]*`/g, ' ')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/https?:\/\/\S+/g, ' ')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/[*_~>#|]/g, ' ')
    .replace(/\s+([,.;:!?])/g, '$1')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 6000)
}

export function falar(
  texto: string,
  opcoes: { id?: string; aoTerminar?: () => void } = {},
): boolean {
  const motor = sintese()
  if (!motor || typeof SpeechSynthesisUtterance === 'undefined') return false

  const limpo = textoParaFala(texto)
  if (!limpo) {
    opcoes.aoTerminar?.()
    return false
  }

  pararFala()
  const atual = ++geracao
  const encerrar = () => {
    if (geracao === atual) avisar({ id: null, falando: false })
    opcoes.aoTerminar?.()
  }

  const fala = new SpeechSynthesisUtterance(limpo)
  const voz = vozPtBr()
  if (voz) {
    fala.voice = voz
    fala.lang = voz.lang
  } else {
    fala.lang = 'pt-BR'
  }
  fala.rate = 1.02
  fala.pitch = 1.05
  fala.onend = encerrar
  fala.onerror = encerrar
  motor.speak(fala)
  avisar({ id: opcoes.id ?? null, falando: true })
  return true
}

export async function falarNeural(
  obterAudio: () => Promise<Blob>,
  opcoes: { id?: string; aoTerminar?: () => void } = {},
): Promise<boolean> {
  pararFala()
  const atual = ++geracao

  let blob: Blob
  try {
    blob = await obterAudio()
  } catch {
    return false
  }
  if (geracao !== atual) throw new FalaCancelada()

  const url = URL.createObjectURL(blob)
  const audio = new Audio(url)
  audioAtual = audio
  urlAudio = url

  const encerrar = () => {
    if (urlAudio === url) {
      URL.revokeObjectURL(url)
      urlAudio = null
    }
    if (audioAtual === audio) audioAtual = null
    if (geracao === atual) avisar({ id: null, falando: false })
    opcoes.aoTerminar?.()
  }

  audio.onended = encerrar
  audio.onerror = encerrar
  try {
    await audio.play()
  } catch {
    encerrar()
    return false
  }
  avisar({ id: opcoes.id ?? null, falando: true })
  return true
}

export function pararFala(): void {
  geracao += 1
  sintese()?.cancel()
  if (audioAtual) {
    audioAtual.pause()
    audioAtual.src = ''
    audioAtual = null
  }
  if (urlAudio) {
    URL.revokeObjectURL(urlAudio)
    urlAudio = null
  }
  avisar({ id: null, falando: false })
}
