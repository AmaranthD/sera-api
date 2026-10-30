import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import type { Session } from '@supabase/supabase-js'
import type { ApiSera } from '../../api/sera'
import { SessaoContext, type ValorSessao } from '../../auth/contexto'
import { PessoaContext, type ValorPessoa } from '../../pessoa/contexto'
import type { Pessoa } from '../../dominios/tipos'
import { Onboarding } from './Onboarding'

const SESSAO = { user: { id: 'u1' } } as Session

function montar(criarPessoa = vi.fn()) {
  const sessao: ValorSessao = {
    sessao: SESSAO,
    carregando: false,
    api: {} as ApiSera,
    entrarComEmail: vi.fn(),
    verificarCodigo: vi.fn(),
    sair: vi.fn().mockResolvedValue(undefined),
  }
  const pessoa: ValorPessoa = {
    pessoa: null,
    carregando: false,
    erro: null,
    recarregar: vi.fn().mockResolvedValue(undefined),
    criarPessoa,
  }
  render(
    <MemoryRouter>
      <SessaoContext.Provider value={sessao}>
        <PessoaContext.Provider value={pessoa}>
          <Onboarding />
        </PessoaContext.Provider>
      </SessaoContext.Provider>
    </MemoryRouter>,
  )
  return { sessao, pessoa, usuario: userEvent.setup() }
}

describe('Onboarding', () => {
  it('exige nome antes de continuar', async () => {
    const criarPessoa = vi.fn()
    const { usuario } = montar(criarPessoa)

    await usuario.click(screen.getByRole('button', { name: 'Começar a conversar' }))

    expect(screen.getByRole('alert')).toHaveTextContent('Como a Sera pode te chamar?')
    expect(criarPessoa).not.toHaveBeenCalled()
  })

  it('exige faixa etária e envia o perfil derivado para criança', async () => {
    const pessoa: Pessoa = {
      id: 'p1',
      nome: 'Ana',
      faixa_etaria: 'crianca',
      perfil: 'crianca_adolescente',
      acesso_vault: false,
      criada_em: '2026-01-01T10:00:00.000Z',
    }
    const criarPessoa = vi.fn().mockResolvedValue(pessoa)
    const { usuario } = montar(criarPessoa)

    await usuario.type(screen.getByLabelText('Seu nome'), 'Ana')
    await usuario.click(screen.getByRole('button', { name: 'Começar a conversar' }))
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Escolha sua faixa etária para continuar.',
    )

    await usuario.click(screen.getByRole('radio', { name: /Criança/ }))
    await usuario.click(screen.getByRole('button', { name: 'Começar a conversar' }))

    expect(criarPessoa).toHaveBeenCalledWith({
      nome: 'Ana',
      faixa_etaria: 'crianca',
      perfil: 'crianca_adolescente',
    })
  })

  it('respeita o jeito escolhido à mão ao trocar a faixa', async () => {
    const criarPessoa = vi.fn()
    const { usuario } = montar(criarPessoa)

    await usuario.type(screen.getByLabelText('Seu nome'), 'Maria')
    await usuario.click(screen.getByRole('radio', { name: /Com calma/ }))
    await usuario.click(screen.getByRole('radio', { name: /Adulto/ }))
    await usuario.click(screen.getByRole('button', { name: 'Começar a conversar' }))

    expect(criarPessoa).toHaveBeenCalledWith({
      nome: 'Maria',
      faixa_etaria: 'adulto',
      perfil: 'idoso_ou_pouco_tecnico',
    })
  })
})
