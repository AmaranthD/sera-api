import { createContext, useContext } from 'react'

export type ModoVoz = 'desligado' | 'voz' | 'so-audio'

export interface ValorVoz {
  modo: ModoVoz
  alternar: () => void
  definir: (modo: ModoVoz) => void
}

export const VozContext = createContext<ValorVoz>({
  modo: 'desligado',
  alternar: () => undefined,
  definir: () => undefined,
})

export function useVoz(): ValorVoz {
  return useContext(VozContext)
}
