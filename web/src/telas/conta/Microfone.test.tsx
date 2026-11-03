import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SecaoMicrofone } from './Microfone'

afterEach(() => {
  vi.restoreAllMocks()
  Object.defineProperty(window, 'isSecureContext', {
    value: false,
    configurable: true,
  })
})

describe('SecaoMicrofone', () => {
  it('pede a permissão e libera o microfone', async () => {
    const parar = vi.fn()
    Object.defineProperty(window, 'isSecureContext', {
      value: true,
      configurable: true,
    })
    Object.defineProperty(navigator, 'mediaDevices', {
      value: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [{ stop: parar }],
        }),
      },
      configurable: true,
    })

    const usuario = userEvent.setup()
    render(<SecaoMicrofone />)
    await usuario.click(
      screen.getByRole('button', { name: 'Permitir microfone' }),
    )

    await waitFor(() =>
      expect(screen.getByText('Liberado')).toBeInTheDocument(),
    )
    expect(parar).toHaveBeenCalled()
  })
})
