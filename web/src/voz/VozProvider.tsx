import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { VozContext, type ModoVoz } from './contexto'

const CHAVE = 'sera:modo-voz'
const ORDEM: ModoVoz[] = ['desligado', 'voz', 'so-audio']

function lerModo(): ModoVoz {
  try {
    const valor = window.localStorage.getItem(CHAVE)
    return valor === 'voz' || valor === 'so-audio' ? valor : 'desligado'
  } catch {
    return 'desligado'
  }
}

export function VozProvider({ children }: { children: ReactNode }) {
  const [modo, setModo] = useState<ModoVoz>(lerModo)

  useEffect(() => {
    try {
      window.localStorage.setItem(CHAVE, modo)
    } catch {
      // Modo privado pode bloquear o localStorage; a sessão continua.
    }
  }, [modo])

  const alternar = useCallback(() => {
    setModo((atual) => ORDEM[(ORDEM.indexOf(atual) + 1) % ORDEM.length] ?? 'desligado')
  }, [])

  const valor = useMemo(
    () => ({ modo, alternar, definir: setModo }),
    [modo, alternar],
  )

  return <VozContext.Provider value={valor}>{children}</VozContext.Provider>
}
