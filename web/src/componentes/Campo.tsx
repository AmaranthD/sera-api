import { useId, type InputHTMLAttributes } from 'react'
import estilos from './Campo.module.css'

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> {
  rotulo: string
  dica?: string
  erro?: string
}

export function Campo({ rotulo, dica, erro, ...resto }: Props) {
  const id = useId()
  const idDica = dica ? `${id}-dica` : undefined
  const idErro = erro ? `${id}-erro` : undefined
  return (
    <div className={estilos.campo}>
      <label className={estilos.rotulo} htmlFor={id}>
        {rotulo}
      </label>
      <input
        id={id}
        className={estilos.entrada}
        aria-invalid={erro ? true : undefined}
        aria-describedby={[idDica, idErro].filter(Boolean).join(' ') || undefined}
        {...resto}
      />
      {dica ? (
        <span className={estilos.dica} id={idDica}>
          {dica}
        </span>
      ) : null}
      {erro ? (
        <span className={estilos.erro} id={idErro} role="alert">
          {erro}
        </span>
      ) : null}
    </div>
  )
}
