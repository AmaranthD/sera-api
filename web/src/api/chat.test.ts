import { http as mswHttp, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import type { EventoChat } from '../dominios/tipos'
import { converterEvento, transmitirChat } from './chat'
import { ClienteHttp } from './http'
import { ErroProtocoloSse } from './sse'

const servidor = setupServer()

beforeAll(() => servidor.listen({ onUnhandledFrame: 'error' }))
afterEach(() => servidor.resetHandlers())
afterAll(() => servidor.close())

function cliente() {
  return new ClienteHttp({
    baseUrl: 'https://api.test',
    obterToken: async () => 'token',
  })
}

const SSE_COMPLETO = [
  'event: start',
  'data: {"conversa_id":"c1","mensagem_id":"m1"}',
  '',
  'event: token',
  'data: {"texto":"Olá"}',
  '',
  'event: token',
  'data: {"texto":", Maria"}',
  '',
  'event: done',
  'data: {"conversa_id":"c1","mensagem_id":"m2","modelo":"z-ai/glm","uso":{"prompt_tokens":10,"completion_tokens":5,"total_tokens":15}}',
  '',
  '',
].join('\n')

describe('converterEvento', () => {
  it('converte start, token e done', () => {
    expect(
      converterEvento({
        evento: 'start',
        dados: { conversa_id: 'c1', mensagem_id: 'm1' },
      }),
    ).toEqual({ tipo: 'start', conversaId: 'c1', mensagemId: 'm1' })

    expect(converterEvento({ evento: 'token', dados: { texto: 'oi' } })).toEqual({
      tipo: 'token',
      texto: 'oi',
    })

    expect(
      converterEvento({
        evento: 'done',
        dados: {
          conversa_id: 'c1',
          mensagem_id: 'm2',
          modelo: 'x',
          uso: { total_tokens: 3 },
        },
      }),
    ).toMatchObject({
      tipo: 'done',
      conversaId: 'c1',
      modelo: 'x',
      uso: { total_tokens: 3 },
    })
  })

  it('converte error e ignora evento desconhecido', () => {
    expect(
      converterEvento({
        evento: 'error',
        dados: { codigo: 'llm_falhou', detalhe: 'caiu' },
      }),
    ).toEqual({
      tipo: 'error',
      codigo: 'llm_falhou',
      detalhe: 'caiu',
    })
    expect(converterEvento({ evento: 'ping', dados: {} })).toBeNull()
  })

  it('recusa start sem ids', () => {
    expect(() =>
      converterEvento({ evento: 'start', dados: { conversa_id: 'c1' } }),
    ).toThrow()
  })

  it('recusa evento conhecido que não é JSON', () => {
    expect(() => converterEvento({ evento: 'token', dados: 'texto puro' })).toThrow(
      ErroProtocoloSse,
    )
  })
})

describe('transmitirChat', () => {
  it('entrega eventos em ordem e termina no done', async () => {
    servidor.use(
      mswHttp.post('https://api.test/chat', () =>
        HttpResponse.text(SSE_COMPLETO, {
          headers: { 'Content-Type': 'text/event-stream' },
        }),
      ),
    )

    const recebidos: EventoChat[] = []
    await transmitirChat(cliente(), { mensagem: 'Oi', conversaId: 'c1' }, (evento) =>
      recebidos.push(evento),
    )

    expect(recebidos.map((evento) => evento.tipo)).toEqual([
      'start',
      'token',
      'token',
      'done',
    ])
    const texto = recebidos
      .filter((evento) => evento.tipo === 'token')
      .map((evento) => (evento.tipo === 'token' ? evento.texto : ''))
      .join('')
    expect(texto).toBe('Olá, Maria')
  })

  it('propaga error do SSE sem exigir done', async () => {
    servidor.use(
      mswHttp.post('https://api.test/chat', () =>
        HttpResponse.text(
          'event: start\ndata: {"conversa_id":"c1","mensagem_id":"m1"}\n\nevent: error\ndata: {"codigo":"llm_falhou","detalhe":"sem provedor"}\n\n',
          { headers: { 'Content-Type': 'text/event-stream' } },
        ),
      ),
    )

    const recebidos: EventoChat[] = []
    await transmitirChat(cliente(), { mensagem: 'Oi' }, (evento) =>
      recebidos.push(evento),
    )

    expect(recebidos.at(-1)).toEqual({
      tipo: 'error',
      codigo: 'llm_falhou',
      detalhe: 'sem provedor',
    })
  })

  it('falha quando o stream termina sem done', async () => {
    servidor.use(
      mswHttp.post('https://api.test/chat', () =>
        HttpResponse.text('event: token\ndata: {"texto":"pela metade"}\n\n', {
          headers: { 'Content-Type': 'text/event-stream' },
        }),
      ),
    )

    await expect(
      transmitirChat(cliente(), { mensagem: 'Oi' }, () => {}),
    ).rejects.toMatchObject({
      status: 0,
      codigo: 'stream_incompleto',
    })
  })

  it('mapeia erro HTTP antes do stream', async () => {
    servidor.use(
      mswHttp.post('https://api.test/chat', () =>
        HttpResponse.json(
          { detail: 'conversa não encontrada' },
          {
            status: 404,
          },
        ),
      ),
    )

    await expect(
      transmitirChat(cliente(), { mensagem: 'Oi' }, () => {}),
    ).rejects.toMatchObject({ status: 404, codigo: 'nao_encontrado' })
  })

  it('envia o corpo esperado pelo contrato', async () => {
    let corpo: unknown = null
    servidor.use(
      mswHttp.post('https://api.test/chat', async ({ request }) => {
        corpo = await request.json()
        return HttpResponse.text(SSE_COMPLETO, {
          headers: { 'Content-Type': 'text/event-stream' },
        })
      }),
    )

    const enviar = vi.fn()
    await transmitirChat(cliente(), { mensagem: 'Oi', conversaId: 'c1' }, enviar)

    expect(corpo).toEqual({
      mensagem: 'Oi',
      conversa_id: 'c1',
      stream: true,
    })
  })
})
