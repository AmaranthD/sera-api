import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import type { ApiSera } from '../../api/sera'
import { SessaoContext, type ValorSessao } from '../../auth/contexto'
import { PessoaContext, type ValorPessoa } from '../../pessoa/contexto'
import { Login } from './Login'

function montar(extra: Partial<ValorSessao> = {}) {
  const sessao: ValorSessao = {
    sessao: null,
    carregando: false,
    api: {} as ApiSera,
    entrarComEmail: vi.fn().mockResolvedValue(undefined),
    verificarCodigo: vi.fn().mockResolvedValue(undefined),
    sair: vi.fn().mockResolvedValue(undefined),
    ...extra,
  }
  const pessoa: ValorPessoa = {
    pessoa: null,
    carregando: false,
    erro: null,
    recarregar: vi.fn().mockResolvedValue(undefined),
    criarPessoa: vi.fn(),
  }
  render(
    <MemoryRouter>
      <SessaoContext.Provider value={sessao}>
        <PessoaContext.Provider value={pessoa}>
          <Login />
        </PessoaContext.Provider>
      </SessaoContext.Provider>
    </MemoryRouter>,
  )
  return { sessao, pessoa, usuario: userEvent.setup() }
}

describe('Login', () => {
  it('recusa e-mail inválido sem chamar o Supabase', async () => {
    const { sessao, usuario } = montar()
    await usuario.type(screen.getByLabelText('E-mail'), 'maria')
    await usuario.click(screen.getByRole('button', { name: 'Receber link de acesso' }))

    expect(screen.getByText(/Digite um e-mail válido/)).toBeInTheDocument()
    expect(sessao.entrarComEmail).not.toHaveBeenCalled()
  })

  it('envia o link e mostra a etapa do código', async () => {
    const { sessao, usuario } = montar()
    await usuario.type(screen.getByLabelText('E-mail'), '  Maria@Exemplo.com ')
    await usuario.click(screen.getByRole('button', { name: 'Receber link de acesso' }))

    expect(sessao.entrarComEmail).toHaveBeenCalledWith('maria@exemplo.com')
    expect(
      await screen.findByRole('heading', { name: 'Confira seu e-mail' }),
    ).toBeInTheDocument()
    expect(screen.getByText('maria@exemplo.com')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Reenviar acesso em \d+s/ }),
    ).toBeDisabled()
  })

  it('verifica o código de 6 dígitos', async () => {
    const { sessao, usuario } = montar()
    await usuario.type(screen.getByLabelText('E-mail'), 'maria@exemplo.com')
    await usuario.click(screen.getByRole('button', { name: 'Receber link de acesso' }))
    await screen.findByRole('heading', { name: 'Confira seu e-mail' })

    const codigo = screen.getByLabelText('Código de 6 dígitos')
    await usuario.type(codigo, '123')
    expect(screen.getByRole('button', { name: 'Entrar com código' })).toBeDisabled()

    await usuario.type(codigo, '456')
    await usuario.click(screen.getByRole('button', { name: 'Entrar com código' }))

    expect(sessao.verificarCodigo).toHaveBeenCalledWith('maria@exemplo.com', '123456')
  })

  it('mostra o erro sem apagar o e-mail digitado', async () => {
    const { usuario } = montar({
      entrarComEmail: vi.fn().mockRejectedValue(new Error('Muitos pedidos de acesso.')),
    })
    await usuario.type(screen.getByLabelText('E-mail'), 'maria@exemplo.com')
    await usuario.click(screen.getByRole('button', { name: 'Receber link de acesso' }))

    expect(await screen.findByText('Muitos pedidos de acesso.')).toBeInTheDocument()
    expect(screen.getByLabelText('E-mail')).toHaveValue('maria@exemplo.com')
  })
})
