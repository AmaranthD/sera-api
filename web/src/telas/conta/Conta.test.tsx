import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ApiSera } from '../../api/sera'
import { SessaoContext } from '../../auth/contexto'
import type { Ajuste, Memoria, Pessoa } from '../../dominios/tipos'
import { PessoaContext } from '../../pessoa/contexto'
import { Conta } from './Conta'

const PESSOA: Pessoa = {
  id: 'maria',
  nome: 'Maria',
  faixa_etaria: 'adulto',
  perfil: 'padrao',
  acesso_vault: true,
  criada_em: '2026-10-01T10:00:00Z',
}

const MEMORIA: Memoria = {
  id: 'mem-1',
  pessoa_id: 'maria',
  texto: 'Gosta de jazz',
  categoria: 'gostos',
  criada_em: '2026-10-02T10:00:00Z',
}

const AJUSTE: Ajuste = {
  id: 'aj-1',
  pessoa_id: 'maria',
  tipo: 'apelido',
  texto: 'Mãe Sera',
  valor: null,
  origem: 'conversa',
  criada_em: '2026-10-03T10:00:00Z',
}

function montar(overrides: Record<string, unknown> = {}) {
  const api = {
    saude: vi.fn().mockResolvedValue({ status: 'ok' }),
    listarMemorias: vi.fn().mockResolvedValue([MEMORIA]),
    listarAjustes: vi.fn().mockResolvedValue([AJUSTE]),
    atualizarMemoria: vi
      .fn()
      .mockResolvedValue({ ...MEMORIA, texto: 'Gosta de blues' }),
    apagarMemoria: vi.fn().mockResolvedValue(null),
    atualizarAjuste: vi.fn().mockResolvedValue({ ...AJUSTE, texto: 'Sera' }),
    apagarAjuste: vi.fn().mockResolvedValue(null),
    obterTextoDiario: vi.fn().mockResolvedValue({
      ativo: false,
      hora: '07:00',
      fuso: 'America/Sao_Paulo',
      conversa_id: null,
      ultimo_envio_dia: null,
    }),
    salvarTextoDiario: vi.fn().mockResolvedValue({
      ativo: true,
      hora: '07:00',
      fuso: 'America/Sao_Paulo',
      conversa_id: null,
      ultimo_envio_dia: null,
    }),
    enviarTextoDiarioAgora: vi.fn().mockResolvedValue({
      conversa_id: 'conversa-1',
      mensagem_id: 'mensagem-1',
      dia: '2026-11-04',
      enviados: 0,
      falhas: 0,
    }),
    exportarDados: vi.fn().mockResolvedValue({
      gerado_em: '2026-11-01T10:00:00Z',
      pessoa: PESSOA,
      memorias: [MEMORIA],
      ajustes: [AJUSTE],
      conversas: [],
    }),
    ...overrides,
  } as unknown as ApiSera

  const sessao = {
    sessao: { user: { email: 'maria@exemplo.com' } },
    carregando: false,
    api,
    entrarComEmail: vi.fn(),
    verificarCodigo: vi.fn(),
    sair: vi.fn(),
  } as never

  const pessoa = {
    pessoa: PESSOA,
    carregando: false,
    erro: null,
    recarregar: vi.fn(),
    criarPessoa: vi.fn(),
  }

  render(
    <MemoryRouter>
      <SessaoContext.Provider value={sessao}>
        <PessoaContext.Provider value={pessoa}>
          <Conta />
        </PessoaContext.Provider>
      </SessaoContext.Provider>
    </MemoryRouter>,
  )

  return { api, usuario: userEvent.setup() }
}

beforeEach(() => {
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  Object.defineProperty(URL, 'createObjectURL', {
    configurable: true,
    value: vi.fn(() => 'blob:sera'),
  })
  Object.defineProperty(URL, 'revokeObjectURL', {
    configurable: true,
    value: vi.fn(),
  })
})

describe('Conta', () => {
  it('lista o que a Sera aprendeu', async () => {
    const { api } = montar()

    expect(await screen.findByText('Gosta de jazz')).toBeInTheDocument()
    expect(screen.getByText('Mãe Sera')).toBeInTheDocument()
    expect(api.listarMemorias).toHaveBeenCalledWith('maria')
    expect(api.listarAjustes).toHaveBeenCalledWith('maria')
  })

  it('edita uma memória no lugar', async () => {
    const { api, usuario } = montar()

    await screen.findByText('Gosta de jazz')
    await usuario.click(
      screen.getByRole('button', { name: 'Editar memória: Gosta de jazz' }),
    )

    const campo = screen.getByLabelText('Fato')
    await usuario.clear(campo)
    await usuario.type(campo, 'Gosta de blues')
    await usuario.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => {
      expect(api.atualizarMemoria).toHaveBeenCalledWith('maria', 'mem-1', {
        texto: 'Gosta de blues',
        categoria: 'gostos',
      })
    })
    expect(await screen.findByText('Gosta de blues')).toBeInTheDocument()
  })

  it('pede confirmação antes de apagar uma memória', async () => {
    const { api, usuario } = montar()

    await screen.findByText('Gosta de jazz')
    await usuario.click(
      screen.getByRole('button', { name: 'Apagar memória: Gosta de jazz' }),
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Apagar esta memória?')

    await usuario.click(screen.getByRole('button', { name: 'Sim, apagar' }))

    await waitFor(() => {
      expect(api.apagarMemoria).toHaveBeenCalledWith('maria', 'mem-1')
    })
    await waitFor(() => {
      expect(screen.queryByText('Gosta de jazz')).not.toBeInTheDocument()
    })
  })

  it('edita um ajuste de texto', async () => {
    const { api, usuario } = montar()

    await screen.findByText('Mãe Sera')
    await usuario.click(screen.getByRole('button', { name: 'Editar ajuste: Apelido' }))

    const campo = screen.getByLabelText('Apelido')
    await usuario.clear(campo)
    await usuario.type(campo, 'Sera')
    await usuario.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => {
      expect(api.atualizarAjuste).toHaveBeenCalledWith('maria', 'aj-1', {
        texto: 'Sera',
      })
    })
  })

  it('baixa os dados em JSON', async () => {
    const { api, usuario } = montar()

    await usuario.click(
      screen.getByRole('button', { name: 'Baixar meus dados (JSON)' }),
    )

    await waitFor(() => {
      expect(api.exportarDados).toHaveBeenCalledWith('maria')
    })
    expect(URL.createObjectURL).toHaveBeenCalled()
  })

  it('mostra estado vazio quando não há nada aprendido', async () => {
    montar({
      listarMemorias: vi.fn().mockResolvedValue([]),
      listarAjustes: vi.fn().mockResolvedValue([]),
    })

    expect(
      await screen.findByText(/Ainda não guardei nada sobre você/),
    ).toBeInTheDocument()
    expect(screen.getByText(/Nenhum ajuste ainda/)).toBeInTheDocument()
  })
})
