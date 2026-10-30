import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Composer } from './Composer'

function montar(extra: Partial<Parameters<typeof Composer>[0]> = {}) {
  const props = {
    valor: 'Oi, Sera',
    aoMudar: vi.fn(),
    aoEnviar: vi.fn(),
    aoParar: vi.fn(),
    ocupado: false,
    online: true,
    ...extra,
  }
  render(<Composer {...props} />)
  return { props, usuario: userEvent.setup() }
}

describe('Composer', () => {
  it('envia com Enter e não quebra linha', async () => {
    const { props, usuario } = montar()
    const campo = screen.getByLabelText('Escreva sua mensagem para a Sera')
    await usuario.click(campo)
    await usuario.keyboard('{Enter}')

    expect(props.aoEnviar).toHaveBeenCalledWith('Oi, Sera')
  })

  it('Shift + Enter não envia', async () => {
    const { props, usuario } = montar()
    const campo = screen.getByLabelText('Escreva sua mensagem para a Sera')
    await usuario.click(campo)
    await usuario.keyboard('{Shift>}{Enter}{/Shift}')

    expect(props.aoEnviar).not.toHaveBeenCalled()
  })

  it('não envia mensagem só com espaços', async () => {
    const { props, usuario } = montar({ valor: '   ' })
    await usuario.click(screen.getByLabelText('Escreva sua mensagem para a Sera'))
    await usuario.keyboard('{Enter}')
    expect(props.aoEnviar).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Enviar mensagem' })).toBeDisabled()
  })

  it('troca enviar por parar durante a resposta', async () => {
    const { props, usuario } = montar({ ocupado: true })
    await usuario.click(screen.getByRole('button', { name: 'Parar a resposta' }))
    expect(props.aoParar).toHaveBeenCalledTimes(1)
    expect(
      screen.queryByRole('button', { name: 'Enviar mensagem' }),
    ).not.toBeInTheDocument()
  })

  it('bloqueia o campo sem conexão', () => {
    montar({ online: false })
    expect(screen.getByLabelText('Escreva sua mensagem para a Sera')).toBeDisabled()
    expect(screen.getByText('Sem conexão para enviar.')).toBeInTheDocument()
  })

  it('mostra o contador perto do limite', () => {
    montar({ valor: 'a'.repeat(7001) })
    expect(screen.getByText('7001/8000')).toBeInTheDocument()
  })
})
