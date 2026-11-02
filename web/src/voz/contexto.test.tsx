import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { useVoz } from './contexto'
import { VozProvider } from './VozProvider'

function Sonda() {
  const { modo, alternar } = useVoz()
  return (
    <button type="button" onClick={alternar}>
      {modo}
    </button>
  )
}

afterEach(() => window.localStorage.clear())

describe('VozProvider', () => {
  it('alterna desligado → voz → só áudio → desligado', async () => {
    const usuario = userEvent.setup()
    render(
      <VozProvider>
        <Sonda />
      </VozProvider>,
    )

    const botao = screen.getByRole('button')
    expect(botao).toHaveTextContent('desligado')
    await usuario.click(botao)
    expect(botao).toHaveTextContent('voz')
    await usuario.click(botao)
    expect(botao).toHaveTextContent('so-audio')
    await usuario.click(botao)
    expect(botao).toHaveTextContent('desligado')
  })
})
