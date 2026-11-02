interface ResultadoFala {
  readonly isFinal: boolean
  readonly 0?: { transcript?: string }
}

interface EventoResultado {
  readonly resultIndex: number
  readonly results: {
    readonly length: number
    readonly [indice: number]: ResultadoFala | undefined
  }
}

interface EventoErro {
  readonly error: string
}

interface Reconhecedor {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((evento: EventoResultado) => void) | null
  onerror: ((evento: EventoErro) => void) | null
  onend: (() => void) | null
  start(): void
  stop(): void
  abort(): void
}

type ConstrutorReconhecedor = new () => Reconhecedor

function construtor(): ConstrutorReconhecedor | null {
  if (typeof window === 'undefined') return null
  const janela = window as unknown as {
    SpeechRecognition?: ConstrutorReconhecedor
    webkitSpeechRecognition?: ConstrutorReconhecedor
  }
  return janela.SpeechRecognition ?? janela.webkitSpeechRecognition ?? null
}

export interface OpcoesOuvir {
  aoTexto: (texto: string, final: boolean) => void
  aoErro?: (erro: string) => void
  aoFim?: () => void
}

export interface Ouvinte {
  parar(): void
}

export function reconhecimentoSuportado(): boolean {
  return construtor() !== null
}

const CHAVE_AVISO = 'sera:voz-aviso'

/**
 * O Web Speech API usa o serviço do navegador; em alguns navegadores o áudio
 * sai do dispositivo. Pede consentimento uma única vez por navegador.
 */
export function confirmarUsoDaVoz(): boolean {
  if (typeof window === 'undefined') return false
  try {
    if (window.localStorage.getItem(CHAVE_AVISO) === 'ok') return true
    const aceito = window.confirm(
      'Para ditar, o navegador vai ouvir o microfone e pode enviar o áudio ' +
        'para o serviço dele. Nenhum áudio é gravado pela Sera. Continuar?',
    )
    if (aceito) window.localStorage.setItem(CHAVE_AVISO, 'ok')
    return aceito
  } catch {
    return true
  }
}

export function ouvir(opcoes: OpcoesOuvir): Ouvinte | null {
  const Ctor = construtor()
  if (!Ctor) return null

  const reconhecedor = new Ctor()
  reconhecedor.lang = 'pt-BR'
  reconhecedor.continuous = true
  reconhecedor.interimResults = true

  let ativo = true

  reconhecedor.onresult = (evento) => {
    let final = ''
    let parcial = ''
    for (let indice = evento.resultIndex; indice < evento.results.length; indice += 1) {
      const resultado = evento.results[indice]
      const texto = resultado?.[0]?.transcript?.trim() ?? ''
      if (!texto) continue
      if (resultado?.isFinal) final = `${final} ${texto}`.trim()
      else parcial = `${parcial} ${texto}`.trim()
    }
    if (final) opcoes.aoTexto(final, true)
    else if (parcial) opcoes.aoTexto(parcial, false)
  }

  reconhecedor.onerror = (evento) => {
    if (evento.error !== 'aborted' && evento.error !== 'no-speech') {
      opcoes.aoErro?.(evento.error)
    }
  }

  reconhecedor.onend = () => {
    if (!ativo) return
    ativo = false
    opcoes.aoFim?.()
  }

  try {
    reconhecedor.start()
  } catch {
    return null
  }

  return {
    parar: () => {
      if (!ativo) return
      ativo = false
      try {
        reconhecedor.stop()
      } catch {
        // O navegador pode já ter encerrado sozinho.
      }
      opcoes.aoFim?.()
    },
  }
}

export function mensagemDeErroVoz(erro: string): string {
  if (erro === 'not-allowed' || erro === 'service-not-allowed') {
    return 'Permissão de microfone negada. Libere nas permissões do site.'
  }
  if (erro === 'audio-capture') return 'Nenhum microfone encontrado.'
  if (erro === 'network') return 'Sem conexão para o reconhecimento de voz.'
  if (erro === 'no-speech') return 'Não ouvi nada. Tente de novo.'
  return 'Não consegui ouvir. Tente de novo.'
}
