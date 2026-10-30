import type { EntradaChat, EventoChat, UsoLLM } from '../dominios/tipos'
import { ErroApi } from './erros'
import type { ClienteHttp } from './http'
import { ErroProtocoloSse, lerEventosSse, type EventoSse } from './sse'

const CONHECIDOS = new Set(['start', 'token', 'done', 'error'])

function texto(dados: Record<string, unknown>, chave: string): string {
  const valor = dados[chave]
  if (typeof valor !== 'string' || !valor) {
    throw new ErroProtocoloSse(`Evento sem o campo "${chave}".`)
  }
  return valor
}

/** Converte o evento cru do SSE no contrato tipado do app. */
export function converterEvento(evento: EventoSse): EventoChat | null {
  if (!evento.dados || typeof evento.dados !== 'object') {
    if (CONHECIDOS.has(evento.evento)) {
      throw new ErroProtocoloSse(`Evento ${evento.evento} veio sem JSON válido.`)
    }
    return null
  }
  const dados = evento.dados as Record<string, unknown>
  switch (evento.evento) {
    case 'start':
      return {
        tipo: 'start',
        conversaId: texto(dados, 'conversa_id'),
        mensagemId: texto(dados, 'mensagem_id'),
      }
    case 'token':
      return {
        tipo: 'token',
        texto: typeof dados.texto === 'string' ? dados.texto : '',
      }
    case 'done':
      return {
        tipo: 'done',
        conversaId: texto(dados, 'conversa_id'),
        mensagemId: texto(dados, 'mensagem_id'),
        modelo: typeof dados.modelo === 'string' ? dados.modelo : '',
        uso: dados.uso && typeof dados.uso === 'object' ? (dados.uso as UsoLLM) : null,
      }
    case 'error':
      return {
        tipo: 'error',
        codigo: typeof dados.codigo === 'string' ? dados.codigo : 'desconhecido',
        detalhe:
          typeof dados.detalhe === 'string'
            ? dados.detalhe
            : 'A Sera não conseguiu responder.',
      }
    default:
      return null
  }
}

export async function transmitirChat(
  http: ClienteHttp,
  entrada: EntradaChat,
  aoEvento: (evento: EventoChat) => void,
  sinal?: AbortSignal,
): Promise<void> {
  const resposta = await http.abrir('/chat', {
    metodo: 'POST',
    corpo: {
      mensagem: entrada.mensagem,
      conversa_id: entrada.conversaId,
      stream: true,
    },
    sinal,
  })

  const tipo = resposta.headers.get('content-type') ?? ''
  if (!resposta.body || !tipo.includes('text/event-stream')) {
    throw new ErroApi(
      502,
      'protocolo',
      'A resposta da Sera veio em um formato inesperado.',
    )
  }

  let viuFim = false
  for await (const cru of lerEventosSse(resposta.body)) {
    const evento = converterEvento(cru)
    if (!evento) continue
    if (evento.tipo === 'done' || evento.tipo === 'error') {
      viuFim = true
    }
    aoEvento(evento)
  }

  if (!viuFim && !sinal?.aborted) {
    throw new ErroApi(
      0,
      'stream_incompleto',
      'A conexão caiu antes do fim da resposta.',
    )
  }
}
