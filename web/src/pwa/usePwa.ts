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

export interface ValorInstalacao {
  podeInstalar: boolean
  instalado: boolean
  ehIOS: boolean
  instalar: () => Promise<void>
}

export function useInstalacao(): ValorInstalacao {
  const [evento, setEvento] = useState<EventoAntesDeInstalar | null>(null)
  const [instalado, setInstalado] = useState(estaInstalado)
  const [ehIOS] = useState(() => {
    if (typeof navigator === 'undefined') return false
    return (
      /iphone|ipad|ipod/i.test(navigator.userAgent) &&
      !/crios|fxios/i.test(navigator.userAgent)
    )
  })

  useEffect(() => {
    const aoPoderInstalar = (bruto: Event) => {
      bruto.preventDefault()
      setEvento(bruto as EventoAntesDeInstalar)
    }
    const aoInstalar = () => {
      setInstalado(true)
      setEvento(null)
    }
    window.addEventListener('beforeinstallprompt', aoPoderInstalar)
    window.addEventListener('appinstalled', aoInstalar)
    return () => {
      window.removeEventListener('beforeinstallprompt', aoPoderInstalar)
      window.removeEventListener('appinstalled', aoInstalar)
    }
  }, [])

  const instalar = async () => {
    if (!evento) return
    await evento.prompt()
    const escolha = await evento.userChoice
    if (escolha.outcome === 'accepted') {
      setInstalado(true)
    }
    setEvento(null)
  }

  return {
    podeInstalar: Boolean(evento),
    instalado,
    ehIOS,
    instalar,
  }
}
