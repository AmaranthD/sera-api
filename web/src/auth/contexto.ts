import { createContext, useContext } from 'react'
import type { Session } from '@supabase/supabase-js'
import type { ApiSera } from '../api/sera'

export interface ValorSessao {
  sessao: Session | null
  carregando: boolean
  api: ApiSera
  entrarComEmail: (email: string) => Promise<void>
  verificarCodigo: (email: string, codigo: string) => Promise<void>
  sair: () => Promise<void>
}

export const SessaoContext = createContext<ValorSessao | null>(null)

export function useSessao(): ValorSessao {
  const valor = useContext(SessaoContext)
  if (!valor) {
    throw new Error('useSessao precisa estar dentro de SessaoProvider')
  }
  return valor
}
