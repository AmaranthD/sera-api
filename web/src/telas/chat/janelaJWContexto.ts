import { createContext, useContext } from 'react'

export type AbrirJanela = (url: string, referencia?: string) => void

export const JanelaJWContext = createContext<AbrirJanela | null>(null)

export function useJanelaJW(): AbrirJanela | null {
  return useContext(JanelaJWContext)
}
