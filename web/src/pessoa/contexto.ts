import { createContext, useContext } from 'react'
import type { EntradaPessoa, Pessoa } from '../dominios/tipos'

export interface ValorPessoa {
  pessoa: Pessoa | null
  carregando: boolean
  erro: string | null
  recarregar: () => Promise<void>
  criarPessoa: (entrada: EntradaPessoa) => Promise<Pessoa>
}

export const PessoaContext = createContext<ValorPessoa | null>(null)

export function usePessoa(): ValorPessoa {
  const valor = useContext(PessoaContext)
  if (!valor) {
    throw new Error('usePessoa precisa estar dentro de PessoaProvider')
  }
  return valor
}
