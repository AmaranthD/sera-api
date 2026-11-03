import { createContext, useContext } from 'react'

export type ModoVoz = 'desligado' | 'voz' | 'so-audio'

export interface ValorVoz {
  modo: ModoVoz
  neural: boolean
  alternar: () => void
  definir: (modo: ModoVoz) => void
  definirNeural: (neural: boolean) => void
}

export const VozContext = createContext<ValorVoz>({
  modo: 'desligado',
  neural: false,
  alternar: () => undefined,
  definir: () => undefined,
  definirNeural: () => undefined,
})

export function useVoz(): ValorVoz {
  return useContext(VozContext)
}
