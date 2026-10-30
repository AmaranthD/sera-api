import { describe, expect, it } from 'vitest'
import { ParserSse, lerEventosSse } from './sse'

function fluxo(...pedacos: Uint8Array[]): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controlador) {
      for (const pedaco of pedacos) controlador.enqueue(pedaco)
      controlador.close()
    },
  })
}

describe('ParserSse', () => {
  it('lê dois eventos no mesmo pedaço', () => {
    const parser = new ParserSse()
    const eventos = parser.alimentar(
      'event: token\ndata: {"texto":"Oi"}\n\nevent: done\ndata: {"id":"1"}\n\n',
    )
    expect(eventos).toEqual([
      { evento: 'token', dados: { texto: 'Oi' } },
      { evento: 'done', dados: { id: '1' } },
    ])
  })

  it('guarda um evento partido entre pedaços', () => {
    const parser = new ParserSse()
    expect(parser.alimentar('event: token\ndata: {"texto":"Oi')).toEqual([])
    expect(parser.alimentar('"}\n\n')).toEqual([
      { evento: 'token', dados: { texto: 'Oi' } },
    ])
  })

  it('aceita CRLF, inclusive partido entre pedaços', () => {
    const parser = new ParserSse()
    expect(parser.alimentar('event: token\r')).toEqual([])
    const eventos = parser.alimentar(
      '\ndata: {"texto":"a"}\r\n\r\nevent: token\r\ndata: {"texto":"b"}\r\n\r\n',
    )
    expect(eventos.map((evento) => evento.dados)).toEqual([
      { texto: 'a' },
      { texto: 'b' },
    ])
  })

  it('junta data em várias linhas e ignora comentários', () => {
    const parser = new ParserSse()
    const eventos = parser.alimentar(
      ': keep-alive\nevent: aviso\nid: 7\nretry: 3000\ndata: linha 1\ndata: linha 2\n\n',
    )
    expect(eventos).toEqual([{ evento: 'aviso', dados: 'linha 1\nlinha 2' }])
  })

  it('usa "message" quando não há event', () => {
    const parser = new ParserSse()
    expect(parser.alimentar('data: {"ok":true}\n\n')).toEqual([
      { evento: 'message', dados: { ok: true } },
    ])
  })

  it('finaliza evento sem a linha em branco final', () => {
    const parser = new ParserSse()
    parser.alimentar('event: token\ndata: {"texto":"fim"}')
    expect(parser.finalizar()).toEqual([{ evento: 'token', dados: { texto: 'fim' } }])
    expect(parser.finalizar()).toEqual([])
  })

  it('mantém data em texto puro quando não é JSON', () => {
    const parser = new ParserSse()
    expect(parser.alimentar('event: aviso\ndata: nope\n\n')).toEqual([
      { evento: 'aviso', dados: 'nope' },
    ])
  })
})

describe('lerEventosSse', () => {
  it('lê UTF-8 partido no meio de um acento', async () => {
    const texto = 'event: token\ndata: {"texto":"coração"}\n\nevent: done\ndata: {}\n\n'
    const bytes = new TextEncoder().encode(texto)
    const corte = texto.indexOf('ç') + 1
    const eventos: unknown[] = []
    for await (const evento of lerEventosSse(
      fluxo(bytes.slice(0, corte), bytes.slice(corte)),
    )) {
      eventos.push(evento)
    }
    expect(eventos).toEqual([
      { evento: 'token', dados: { texto: 'coração' } },
      { evento: 'done', dados: {} },
    ])
  })

  it('não perde o último evento sem linha em branco', async () => {
    const bytes = new TextEncoder().encode(
      'event: token\ndata: {"texto":"a"}\n\nevent: token\ndata: {"texto":"b"}',
    )
    const eventos: unknown[] = []
    for await (const evento of lerEventosSse(fluxo(bytes))) {
      eventos.push(evento)
    }
    expect(eventos).toHaveLength(2)
  })
})
