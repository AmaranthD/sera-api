import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { VozContext, type ModoVoz } from './contexto'

const CHAVE = 'sera:modo-voz'
const CHAVE_NEURAL = 'sera:voz-neural'
const ORDEM: ModoVoz[] = ['desligado', 'voz', 'so-audio']

function lerModo(): ModoVoz {
  try {
    const valor = window.localStorage.getItem(CHAVE)
    return valor === 'voz' || valor === 'so-audio' ? valor : 'desligado'
  } catch {
    return 'desligado'
  }
}

function lerNeural(): boolean {
  try {
    return window.localStorage.getItem(CHAVE_NEURAL) === 'ok'
  } catch {
    return false
  }
}

export function VozProvider({ children }: { children: ReactNode }) {
  const [modo, setModo] = useState<ModoVoz>(lerModo)
  const [neural, setNeural] = useState(lerNeural)

  useEffect(() => {
    try {
      window.localStorage.setItem(CHAVE, modo)
    } catch {
      // Modo privado pode bloquear o localStorage; a sessão continua.
    }
  }, [modo])

  useEffect(() => {
    try {
      if (neural) window.localStorage.setItem(CHAVE_NEURAL, 'ok')
      else window.localStorage.removeItem(CHAVE_NEURAL)
    } catch {
      // Sem localStorage, a escolha vale só para esta sessão.
    }
  }, [neural])

  const alternar = useCallback(() => {
    setModo((atual) => ORDEM[(ORDEM.indexOf(atual) + 1) % ORDEM.length] ?? 'desligado')
  }, [])

  const valor = useMemo(
    () => ({
      modo,
      neural,
      alternar,
      definir: setModo,
      definirNeural: setNeural,
    }),
    [modo, neural, alternar],
  )

  return <VozContext.Provider value={valor}>{children}</VozContext.Provider>
}
