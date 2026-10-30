export interface EventoSse {
  evento: string
  dados: unknown
}

export class ErroProtocoloSse extends Error {
  constructor(mensagem: string) {
    super(mensagem)
    this.name = 'ErroProtocoloSse'
  }
}

/**
 * Parser incremental de SSE. Recebe pedaços de texto do stream, devolve
 * eventos completos e guarda o resto no buffer.
 */
export class ParserSse {
  private buffer = ''

  alimentar(pedaco: string): EventoSse[] {
    this.buffer += pedaco.replace(/\r\n/g, '\n')
    const eventos: EventoSse[] = []
    let separador = this.buffer.indexOf('\n\n')
    while (separador !== -1) {
      const bloco = this.buffer.slice(0, separador)
      this.buffer = this.buffer.slice(separador + 2)
      const evento = this.interpretar(bloco)
      if (evento) eventos.push(evento)
      separador = this.buffer.indexOf('\n\n')
    }
    return eventos
  }

  finalizar(): EventoSse[] {
    if (!this.buffer.trim()) {
      this.buffer = ''
      return []
    }
    const bloco = this.buffer.replace(/\r/g, '\n')
    this.buffer = ''
    const evento = this.interpretar(bloco)
    return evento ? [evento] : []
  }

  private interpretar(bloco: string): EventoSse | null {
    let evento = 'message'
    const dados: string[] = []
    for (const linha of bloco.split('\n')) {
      if (!linha || linha.startsWith(':')) continue
      const doisPontos = linha.indexOf(':')
      const campo = doisPontos === -1 ? linha : linha.slice(0, doisPontos)
      let valor = doisPontos === -1 ? '' : linha.slice(doisPontos + 1)
      if (valor.startsWith(' ')) valor = valor.slice(1)
      if (campo === 'event') evento = valor
      else if (campo === 'data') dados.push(valor)
    }
    if (dados.length === 0) return null
    const texto = dados.join('\n')
    try {
      return { evento, dados: JSON.parse(texto) }
    } catch {
      // SSE permite data em texto puro; quem conhece o contrato (chat.ts)
      // decide se aquele evento específico precisa de JSON.
      return { evento, dados: texto }
    }
  }
}

export async function* lerEventosSse(
  corpo: ReadableStream<Uint8Array>,
): AsyncGenerator<EventoSse> {
  const leitor = corpo.getReader()
  const decodificador = new TextDecoder()
  const parser = new ParserSse()
  try {
    while (true) {
      const { done, value } = await leitor.read()
      if (done) break
      const texto = decodificador.decode(value, { stream: true })
      for (const evento of parser.alimentar(texto)) yield evento
    }
    const resto = decodificador.decode()
    if (resto) {
      for (const evento of parser.alimentar(resto)) yield evento
    }
    for (const evento of parser.finalizar()) yield evento
  } finally {
    leitor.releaseLock()
  }
}
