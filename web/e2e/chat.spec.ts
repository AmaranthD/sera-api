import { expect, test } from '@playwright/test'
import { CONVERSA, comSessaoFalsa, rotearApi } from './ajuda'

test.beforeEach(async ({ page }) => {
  await comSessaoFalsa(page)
  await rotearApi(page)
})

test('abre a conversa com sessão salva e mostra o nome', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { level: 2, name: /Oi, Maria/ })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Nova conversa' })).toBeVisible()
})

test('envia mensagem, recebe a resposta e atualiza a URL', async ({ page }) => {
  await page.goto('/')

  const campo = page.getByLabel('Escreva sua mensagem para a Sera')
  await campo.fill('Oi, Sera')
  await campo.press('Enter')

  await expect(page.getByText('Oi, Sera')).toBeVisible()
  await expect(page.getByText('Olá, Maria! Tudo bem?')).toBeVisible()
  await expect(page).toHaveURL(/\/c\/c1$/)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    /Quero conversar sobre o almoço/,
  )
})

test('cada conversa da lista abre a sua rota', async ({ page }) => {
  await page.goto('/')

  await page.getByRole('button', { name: new RegExp(CONVERSA.titulo) }).click()

  await expect(page).toHaveURL(/\/c\/c1$/)
  await expect(page.getByText('Essa conversa ainda não tem mensagens.')).toBeVisible()
})

test('mantém o rascunho e envia só com Enter', async ({ page }) => {
  await page.goto('/')

  const campo = page.getByLabel('Escreva sua mensagem para a Sera')
  await campo.fill('primeira linha')
  await campo.press('Shift+Enter')
  await campo.pressSequentially('segunda linha')

  await expect(campo).toHaveValue('primeira linha\nsegunda linha')
  await expect(page.getByText('Olá, Maria! Tudo bem?')).toHaveCount(0)

  await campo.press('Enter')
  await expect(page.getByText('Olá, Maria! Tudo bem?')).toBeVisible()
})

test('o botão de conta mostra o perfil', async ({ page }) => {
  await page.goto('/conta')

  await expect(page.getByRole('heading', { name: 'Maria Souza' })).toBeVisible()
  await expect(page.getByText('maria@exemplo.com')).toBeVisible()
  await expect(page.getByText('Funcionando')).toBeVisible()
})

test('abre offline com o shell e o composer desabilitado', async ({
  page,
  context,
}) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 2, name: /Oi, Maria/ })).toBeVisible()

  await page.evaluate(async () => {
    await navigator.serviceWorker.ready
    if (!navigator.serviceWorker.controller) {
      await new Promise<void>((resolver) => {
        navigator.serviceWorker.addEventListener('controllerchange', () => resolver())
      })
    }
    await new Promise<void>((resolver) => {
      const conferir = () => {
        if (window.localStorage.getItem('sera.pessoa.v1')) resolver()
        else window.setTimeout(conferir, 50)
      }
      conferir()
    })
  })

  await context.setOffline(true)
  await page.reload()

  await expect(page.getByText(/Sem conexão/).first()).toBeVisible()
  await expect(page.getByLabel('Escreva sua mensagem para a Sera')).toBeDisabled()
  await expect(page.getByRole('heading', { level: 2, name: /Oi, Maria/ })).toBeVisible()
})
