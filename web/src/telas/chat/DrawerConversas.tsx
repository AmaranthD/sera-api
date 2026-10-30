import { useEffect, useRef } from 'react'
import { ConteudoLateral } from './ConteudoLateral'
import estilos from './Chat.module.css'

interface Props {
  aberto: boolean
  aoFechar: () => void
}

export function DrawerConversas({ aberto, aoFechar }: Props) {
  const referencia = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialogo = referencia.current
    if (!dialogo) return
    if (aberto && !dialogo.open) {
      dialogo.showModal()
    } else if (!aberto && dialogo.open) {
      dialogo.close()
    }
  }, [aberto])

  return (
    <dialog
      ref={referencia}
      className={estilos.drawer}
      aria-label="Conversas"
      onCancel={(evento) => {
        evento.preventDefault()
        aoFechar()
      }}
      onClick={(evento) => {
        if (evento.target === referencia.current) aoFechar()
      }}
    >
      <div className={estilos.drawerConteudo}>
        <ConteudoLateral aoNavegar={aoFechar} aoFechar={aoFechar} />
      </div>
    </dialog>
  )
}
