import { useEffect, useState } from 'react'

export function useOnline(): boolean {
  const [online, setOnline] = useState(() =>
    typeof navigator === 'undefined' ? true : navigator.onLine,
  )

  useEffect(() => {
    const aoFicarOnline = () => setOnline(true)
    const aoFicarOffline = () => setOnline(false)
    window.addEventListener('online', aoFicarOnline)
    window.addEventListener('offline', aoFicarOffline)
    return () => {
      window.removeEventListener('online', aoFicarOnline)
      window.removeEventListener('offline', aoFicarOffline)
    }
  }, [])

  return online
}

interface EventoAntesDeInstalar extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

function estaInstalado(): boolean {
  if (typeof window === 'undefined') return false
  if (window.matchMedia('(display-mode: standalone)').matches) return true
  return Boolean((window.navigator as Navigator & { standalone?: boolean }).standalone)
}

// O evento de instalação é único na página. Guardamos no módulo para que a
// página /instalar não perca o evento quando o usuário navega até ela.
let eventoGlobal: EventoAntesDeInstalar | null = null
let instaladoGlobal = false
let inicializado = false
const ouvintes = new Set<() => void>()

function notificar() {
  for (const ouvinte of ouvintes) ouvinte()
}

function inicializar() {
  if (inicializado || typeof window === 'undefined') return
  inicializado = true

  window.addEventListener('beforeinstallprompt', (bruto) => {
    bruto.preventDefault()
    eventoGlobal = bruto as EventoAntesDeInstalar
    notificar()
  })

  window.addEventListener('appinstalled', () => {
    instaladoGlobal = true
    eventoGlobal = null
    notificar()
  })
}

if (typeof window !== 'undefined') inicializar()

export interface ValorInstalacao {
  podeInstalar: boolean
  instalado: boolean
  ehIOS: boolean
  instalar: () => Promise<void>
}

export function useInstalacao(): ValorInstalacao {
  const [, setVersao] = useState(0)
  const [ehIOS] = useState(() => {
    if (typeof navigator === 'undefined') return false
    return (
      /iphone|ipad|ipod/i.test(navigator.userAgent) &&
      !/crios|fxios/i.test(navigator.userAgent)
    )
  })

  useEffect(() => {
    const ouvinte = () => setVersao((valor) => valor + 1)
    ouvintes.add(ouvinte)
    return () => {
      ouvintes.delete(ouvinte)
    }
  }, [])

  const instalar = async () => {
    const evento = eventoGlobal
    if (!evento) return
    await evento.prompt()
    const escolha = await evento.userChoice
    if (escolha.outcome === 'accepted') {
      instaladoGlobal = true
    }
    eventoGlobal = null
    notificar()
  }

  return {
    podeInstalar: Boolean(eventoGlobal),
    instalado: instaladoGlobal || estaInstalado(),
    ehIOS,
    instalar,
  }
}
