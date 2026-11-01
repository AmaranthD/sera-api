import { useEffect, useState } from 'react'
import estilos from './FundoPaladina.module.css'

function prefereMenosMovimento(): boolean {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * Vídeo da paladina atrás do chat. Fica bem apagado de propósito: é um
 * detalhe que só aparece quando a pessoa repara. Sem áudio, sem interação.
 */
export function FundoPaladina() {
  const [reduzido, setReduzido] = useState(prefereMenosMovimento)

  useEffect(() => {
    const consulta = window.matchMedia('(prefers-reduced-motion: reduce)')
    const aoMudar = () => setReduzido(consulta.matches)
    consulta.addEventListener('change', aoMudar)
    return () => consulta.removeEventListener('change', aoMudar)
  }, [])

  return (
    <div className={estilos.fundo} aria-hidden="true">
      <video
        className={estilos.video}
        poster="/fundo/paladina-poster.webp"
        autoPlay={!reduzido}
        loop
        muted
        playsInline
        preload="metadata"
        tabIndex={-1}
        disablePictureInPicture
      >
        <source src="/fundo/paladina.webm" type="video/webm" />
        <source src="/fundo/paladina.mp4" type="video/mp4" />
      </video>
      <div className={estilos.veu} />
      <div className={estilos.grao} />
    </div>
  )
}
