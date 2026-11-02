import { http as mswHttp, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'
import { ClienteHttp } from './http'
import { ApiSera } from './sera'

const servidor = setupServer()

beforeAll(() => servidor.listen({ onUnhandledFrame: 'error' }))
afterEach(() => servidor.resetHandlers())
afterAll(() => servidor.close())

function api() {
  return new ApiSera(
    new ClienteHttp({
      baseUrl: 'https://api.test',
      obterToken: async () => 'token',
    }),
    'https://api.test',
  )
}

describe('ApiSera com job assíncrono', () => {
  it('inicia o job com a fonte e devolve os ids', async () => {
    let corpo: unknown = null
    servidor.use(
      mswHttp.post('https://api.test/chat/job', async ({ request }) => {
        corpo = await request.json()
        return HttpResponse.json(
          {
            conversa_id: 'c1',
            mensagem_id: 'm1',
            resposta_id: 'r1',
            status: 'gerando',
          },
          { status: 202 },
        )
      }),
    )

    const trabalho = await api().iniciarChat({
      mensagem: 'Salmo 23',
      fonte: 'jw',
    })

    expect(corpo).toEqual({ mensagem: 'Salmo 23', fonte: 'jw' })
    expect(trabalho).toEqual({
      conversa_id: 'c1',
      mensagem_id: 'm1',
      resposta_id: 'r1',
      status: 'gerando',
    })
  })

  it('consulta o estado de uma resposta', async () => {
    let caminho = ''
    servidor.use(
      mswHttp.get('https://api.test/chat/job/r1', ({ request }) => {
        caminho = new URL(request.url).pathname
        return HttpResponse.json({
          id: 'r1',
          conversa_id: 'c1',
          papel: 'assistant',
          conteudo: 'Oi',
          status: 'gerando',
          fontes: [],
          criada_em: '2026-11-02T10:00:00+00:00',
        })
      }),
    )

    const mensagem = await api().estadoChat('r1')

    expect(caminho).toBe('/chat/job/r1')
    expect(mensagem.status).toBe('gerando')
  })

  it('cancela o job pelo id da resposta', async () => {
    let caminho = ''
    servidor.use(
      mswHttp.post('https://api.test/chat/job/r1/cancelar', ({ request }) => {
        caminho = new URL(request.url).pathname
        return new HttpResponse(null, { status: 204 })
      }),
    )

    await api().cancelarChat('r1')

    expect(caminho).toBe('/chat/job/r1/cancelar')
  })
})

describe('ApiSera com agenda', () => {
  it('cria compromisso no caminho da pessoa', async () => {
    let caminho = ''
    let corpo: unknown = null
    servidor.use(
      mswHttp.post(
        'https://api.test/pessoas/maria/compromissos',
        async ({ request }) => {
          caminho = new URL(request.url).pathname
          corpo = await request.json()
          return HttpResponse.json(
            {
              id: 'k1',
              pessoa_id: 'maria',
              titulo: 'Consulta',
              descricao: '',
              inicio: '2026-11-10T17:00:00+00:00',
              fim: '2026-11-10T18:00:00+00:00',
              fuso: 'America/Sao_Paulo',
              lembrete_minutos: 10,
              lembrete_em: '2026-11-10T16:50:00+00:00',
              lembrete_enviado_em: null,
              criado_em: '2026-11-02T12:00:00+00:00',
              atualizado_em: '2026-11-02T12:00:00+00:00',
            },
            { status: 201 },
          )
        },
      ),
    )

    const criado = await api().criarCompromisso('maria', {
      titulo: 'Consulta',
      inicio: '2026-11-10T14:00:00-03:00',
      fim: '2026-11-10T15:00:00-03:00',
    })

    expect(caminho).toBe('/pessoas/maria/compromissos')
    expect(corpo).toEqual({
      titulo: 'Consulta',
      inicio: '2026-11-10T14:00:00-03:00',
      fim: '2026-11-10T15:00:00-03:00',
    })
    expect(criado.id).toBe('k1')
  })

  it('remove inscrição pelo endpoint codificado', async () => {
    let url = ''
    servidor.use(
      mswHttp.delete(
        'https://api.test/pessoas/maria/notificacoes/inscricoes',
        ({ request }) => {
          url = request.url
          return new HttpResponse(null, { status: 204 })
        },
      ),
    )

    await api().removerNotificacoes('maria', 'https://push.exemplo/abc?token=1')

    expect(url).toContain('endpoint=https%3A%2F%2Fpush.exemplo%2Fabc%3Ftoken%3D1')
  })

  it('consulta a chave pública de notificações', async () => {
    servidor.use(
      mswHttp.get('https://api.test/notificacoes/chave', () =>
        HttpResponse.json({ chave: 'pub' }),
      ),
    )

    await expect(api().chaveNotificacoes()).resolves.toEqual({
      chave: 'pub',
    })
  })
})
