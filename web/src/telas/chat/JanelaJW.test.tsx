import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { ApiSera } from '../../api/sera'
import { JanelaJWProvider } from './JanelaJW'
import { MensagemMarkdown } from './MensagemMarkdown'

const URL_VERSE = 'https://wol.jw.org/pt/wol/bc/r5/lp-t/1102026210/13/0'

function montar() {
  const api = {
    conteudoJW: vi.fn().mockResolvedValue({
      titulo: 'Atos 20',
      paragrafos: ['Texto do capítulo.', 'Nota de estudo.'],
      url: URL_VERSE,
    }),
  } as unknown as ApiSera

  render(
    <JanelaJWProvider api={api}>
      <MensagemMarkdown texto={`[Atos 20:35](${URL_VERSE})`} />
    </JanelaJWProvider>,
  )
  return { api, usuario: userEvent.setup() }
}

describe('JanelaJW', () => {
  it('abre o link do jw.org em um modal em vez de navegar', async () => {
    const { api, usuario } = montar()
    const link = screen.getByRole('link', { name: 'Atos 20:35' })

    await usuario.click(link)

    expect(api.conteudoJW).toHaveBeenCalledWith(URL_VERSE, 'Atos 20:35')
    expect(await screen.findByText('Atos 20')).toBeInTheDocument()
    expect(await screen.findByText('Texto do capítulo.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Abrir no JW.org' })).toHaveAttribute(
      'href',
      URL_VERSE,
    )
  })

  it('deixa o link marcado como externo abrir em nova aba', async () => {
    const api = {
      conteudoJW: vi.fn(),
    } as unknown as ApiSera
    render(
      <JanelaJWProvider api={api}>
        <MensagemMarkdown texto={`[Ver no JW.org](${URL_VERSE}#externo)`} />
      </JanelaJWProvider>,
    )
    const link = screen.getByRole('link', { name: 'Ver no JW.org' })
    expect(link).toHaveAttribute('href', `${URL_VERSE}#externo`)
    expect(link).toHaveAttribute('target', '_blank')
    expect(api.conteudoJW).not.toHaveBeenCalled()
  })

  it('fecha o modal e libera o link para nova abertura', async () => {
    const { usuario } = montar()

    await usuario.click(screen.getByRole('link', { name: 'Atos 20:35' }))
    await screen.findByText('Texto do capítulo.')
    await usuario.click(screen.getByRole('button', { name: 'Fechar' }))

    await waitFor(() => {
      expect(screen.queryByText('Texto do capítulo.')).not.toBeInTheDocument()
    })
  })
})
