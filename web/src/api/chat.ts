import type { EntradaChat, EventoChat, Fonte, UsoLLM } from '../dominios/tipos'
import { ErroApi } from './erros'
import type { ClienteHttp } from './http'
import { ErroProtocoloSse, lerEventosSse, type EventoSse } from './sse'

const CONHECIDOS = new Set(['start', 'token', 'done', 'error', 'sources'])

function texto(dados: Record<string, unknown>, chave: string): string {
  const valor = dados[chave]
  if (typeof valor !== 'string' || !valor) {
    throw new ErroProtocoloSse(`Evento sem o campo "${chave}".`)
  }
  return valor
}

function listaDeFontes(dados: Record<string, unknown>): Fonte[] {
  const bruto = dados.fontes
  if (!Array.isArray(bruto)) return []
  const vistas = new Set<string>()
  const fontes: Fonte[] = []
  for (const item of bruto) {
    if (!item || typeof item !== 'object') continue
    const registro = item as Record<string, unknown>
    const url = typeof registro.url === 'string' ? registro.url.trim() : ''
    if (!/^https?:\/\//i.test(url) || vistas.has(url)) continue
    vistas.add(url)
    const fonte: Fonte = { url }
    if (typeof registro.titulo === 'string' && registro.titulo) {
      fonte.titulo = registro.titulo
    }
    if (typeof registro.trecho === 'string' && registro.trecho) {
      fonte.trecho = registro.trecho
    }
    if (typeof registro.data === 'string' && registro.data) {
      fonte.data = registro.data
    }
    fontes.push(fonte)
  }
  return fontes
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
    case 'sources':
      return { tipo: 'sources', fontes: listaDeFontes(dados) }
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
      ...(entrada.fonte ? { fonte: entrada.fonte } : {}),
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
