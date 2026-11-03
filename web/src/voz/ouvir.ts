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
  maxAlternatives: number
  onstart: (() => void) | null
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
  aoIniciar?: () => void
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

/** O consentimento é guardado só neste navegador. */
export function temConsentimentoVoz(): boolean {
  if (typeof window === 'undefined') return false
  try {
    return window.localStorage.getItem(CHAVE_AVISO) === 'ok'
  } catch {
    return true
  }
}

export function registrarConsentimentoVoz(): void {
  try {
    window.localStorage.setItem(CHAVE_AVISO, 'ok')
  } catch {
    // Sem localStorage, vale só para esta sessão.
  }
}

export function ouvir(opcoes: OpcoesOuvir): Ouvinte | null {
  const Ctor = construtor()
  if (!Ctor) return null

  const reconhecedor = new Ctor()
  reconhecedor.lang = 'pt-BR'
  // Uma frase por vez é bem mais compatível que contínuo no iOS/Android.
  reconhecedor.continuous = false
  reconhecedor.interimResults = true
  reconhecedor.maxAlternatives = 1

  let ativo = true
  let iniciado = false
  const limite = window.setTimeout(() => {
    if (iniciado) return
    opcoes.aoErro?.('timeout')
    try {
      reconhecedor.abort()
    } catch {
      // Ignora: o navegador pode já ter encerrado.
    }
  }, 5000)

  const encerrar = () => {
    window.clearTimeout(limite)
    if (!ativo) return
    ativo = false
    opcoes.aoFim?.()
  }

  reconhecedor.onstart = () => {
    iniciado = true
    window.clearTimeout(limite)
    opcoes.aoIniciar?.()
  }

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
    window.clearTimeout(limite)
    if (evento.error !== 'aborted' && evento.error !== 'no-speech') {
      opcoes.aoErro?.(evento.error)
    }
  }

  reconhecedor.onend = encerrar

  try {
    reconhecedor.start()
  } catch {
    window.clearTimeout(limite)
    return null
  }

  return {
    parar: () => {
      window.clearTimeout(limite)
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
  if (erro === 'NotFoundError' || erro === 'DevicesNotFoundError') {
    return 'Nenhum microfone encontrado.'
  }
  if (erro === 'NotReadableError') {
    return 'O microfone está sendo usado por outro aplicativo.'
  }
  if (erro === 'network') return 'Sem conexão para o reconhecimento de voz.'
  if (erro === 'no-speech') return 'Não ouvi nada. Tente de novo.'
  if (erro === 'timeout') return 'O microfone não iniciou. Confira a permissão do site.'
  if (erro === 'timeout-permissao') {
    return 'Não recebi a permissão do microfone. Confira as permissões do site.'
  }
  return 'Não consegui ouvir. Tente de novo.'
}
