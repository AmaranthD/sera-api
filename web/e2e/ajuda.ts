import type { Page } from '@playwright/test'

export const CHAVE_SESSAO = 'sb-fake-auth-token'

export const PESSOA = {
  id: 'p1',
  nome: 'Maria Souza',
  faixa_etaria: 'adulto',
  perfil: 'padrao',
  acesso_vault: false,
  criada_em: '2026-01-01T10:00:00.000Z',
}

export const CONVERSA = {
  id: 'c1',
  pessoa_id: 'p1',
  titulo: 'Quero conversar sobre o almoço',
  criada_em: '2026-01-02T10:00:00.000Z',
  atualizada_em: '2026-01-02T10:05:00.000Z',
}

export const SESSAO = {
  access_token: 'token-de-teste',
  refresh_token: 'refresh-de-teste',
  token_type: 'bearer',
  expires_in: 3600,
  expires_at: Math.floor(Date.now() / 1000) + 3600,
  user: {
    id: 'u1',
    aud: 'authenticated',
    role: 'authenticated',
    email: 'maria@exemplo.com',
    email_confirmed_at: '2026-01-01T10:00:00.000Z',
    app_metadata: { provider: 'email', providers: ['email'] },
    user_metadata: {},
    created_at: '2026-01-01T10:00:00.000Z',
  },
}

const SSE = [
  'event: start',
  'data: {"conversa_id":"c1","mensagem_id":"m1"}',
  '',
  'event: token',
  'data: {"texto":"Olá, Maria! "}',
  '',
  'event: token',
  'data: {"texto":"Tudo bem?"}',
  '',
  'event: done',
  'data: {"conversa_id":"c1","mensagem_id":"m2","modelo":"fake-model","uso":null}',
  '',
  '',
].join('\n')

export async function comSessaoFalsa(page: Page) {
  await page.addInitScript(
    ({ chave, sessao }) => {
      window.localStorage.setItem(chave, JSON.stringify(sessao))
    },
    { chave: CHAVE_SESSAO, sessao: SESSAO },
  )
}

/** Simula a API e o Supabase; nenhum pedido sai para a rede. */
export async function rotearApi(page: Page) {
  await page.route('https://fake.supabase.co/**', async (rota) => {
    const url = new URL(rota.request().url())
    if (url.pathname === '/auth/v1/token') {
      await rota.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(SESSAO),
      })
      return
    }
    await rota.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(SESSAO.user),
    })
  })

  await page.route('https://api.e2e.test/**', async (rota) => {
    const pedido = rota.request()
    const url = new URL(pedido.url())

    if (url.pathname === '/chat' && pedido.method() === 'POST') {
      await rota.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: SSE,
      })
      return
    }
    if (url.pathname === '/health') {
      await rota.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'ok' }),
      })
      return
    }
    if (url.pathname === '/pessoas') {
      await rota.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([PESSOA]),
      })
      return
    }
    if (url.pathname === '/pessoas/p1/conversas') {
      await rota.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([CONVERSA]),
      })
      return
    }
    if (url.pathname === '/conversas/c1/mensagens') {
      await rota.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      })
      return
    }
    await rota.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'rota não simulada: ' + url.pathname }),
    })
  })
}
