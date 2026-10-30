import { http as mswHttp, HttpResponse, delay } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { ErroApi } from './erros'
import { ClienteHttp } from './http'

const servidor = setupServer()

beforeAll(() => servidor.listen({ onUnhandledFrame: 'error' }))
afterEach(() => servidor.resetHandlers())
afterAll(() => servidor.close())

function cliente(extras: Partial<ConstructorParameters<typeof ClienteHttp>[0]> = {}) {
  return new ClienteHttp({
    baseUrl: 'https://api.test',
    obterToken: async () => 'token-velho',
    ...extras,
  })
}

describe('ClienteHttp', () => {
  it('manda Bearer e devolve JSON', async () => {
    let autorizacao = ''
    servidor.use(
      mswHttp.get('https://api.test/pessoas', ({ request }) => {
        autorizacao = request.headers.get('authorization') ?? ''
        return HttpResponse.json([{ id: 'p1', nome: 'Maria' }])
      }),
    )

    const resposta = await cliente().json<Array<{ nome: string }>>('/pessoas')

    expect(autorizacao).toBe('Bearer token-velho')
    expect(resposta[0]?.nome).toBe('Maria')
  })

  it('renova o token uma vez e repete o pedido após 401', async () => {
    const autorizacoes: string[] = []
    const renovar = vi.fn(async () => 'token-novo')
    servidor.use(
      mswHttp.get('https://api.test/pessoas', ({ request }) => {
        const atual = request.headers.get('authorization') ?? ''
        autorizacoes.push(atual)
        if (atual === 'Bearer token-velho') {
          return HttpResponse.json({ detail: 'expirado' }, { status: 401 })
        }
        return HttpResponse.json([])
      }),
    )

    await cliente({ renovarToken: renovar }).json('/pessoas')

    expect(renovar).toHaveBeenCalledTimes(1)
    expect(autorizacoes).toEqual(['Bearer token-velho', 'Bearer token-novo'])
  })

  it('devolve erro de sessão quando a renovação falha', async () => {
    servidor.use(
      mswHttp.get('https://api.test/pessoas', () =>
        HttpResponse.json({ detail: 'expirado' }, { status: 401 }),
      ),
    )

    await expect(
      cliente({ renovarToken: async () => null }).json('/pessoas'),
    ).rejects.toMatchObject({ status: 401, codigo: 'sessao_expirada' })
  })

  it('usa o detail da API em 422', async () => {
    servidor.use(
      mswHttp.post('https://api.test/pessoas', () =>
        HttpResponse.json(
          { detail: [{ msg: 'faixa_etaria obrigatória' }] },
          { status: 422 },
        ),
      ),
    )

    await expect(
      cliente().json('/pessoas', { metodo: 'POST', corpo: {} }),
    ).rejects.toMatchObject({
      status: 422,
      message: 'faixa_etaria obrigatória',
    })
  })

  it('traduz falha de rede', async () => {
    servidor.use(mswHttp.get('https://api.test/health', () => HttpResponse.error()))

    await expect(cliente().json('/health')).rejects.toMatchObject({
      status: 0,
      codigo: 'rede',
    })
  })

  it('traduz tempo esgotado', async () => {
    servidor.use(
      mswHttp.get('https://api.test/health', async () => {
        await delay(80)
        return HttpResponse.json({ status: 'ok' })
      }),
    )

    try {
      await cliente().json('/health', { tempoLimiteMs: 10 })
      expect.unreachable('deveria ter falhado')
    } catch (erro) {
      expect(erro).toBeInstanceOf(ErroApi)
      expect(erro).toMatchObject({ status: 0, codigo: 'tempo_esgotado' })
    }
  })

  it('trata 204 sem corpo', async () => {
    servidor.use(
      mswHttp.delete(
        'https://api.test/memorias/1',
        () =>
          new HttpResponse(null, {
            status: 204,
          }),
      ),
    )

    await expect(
      cliente().json('/memorias/1', { metodo: 'DELETE' }),
    ).resolves.toBeNull()
  })
})
