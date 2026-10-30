import type { ButtonHTMLAttributes, ReactNode } from 'react'
import estilos from './Botao.module.css'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: 'primario' | 'secundario' | 'fantasma' | 'perigo'
  carregando?: boolean
  icone?: ReactNode
  larguraTotal?: boolean
}

export function Botao({
  variante = 'primario',
  carregando = false,
  icone,
  larguraTotal = false,
  children,
  className,
  disabled,
  ...resto
}: Props) {
  const classes = [
    estilos.botao,
    estilos[variante],
    larguraTotal ? estilos.larguraTotal : '',
    className,
  ]
    .filter(Boolean)
    .join(' ')
  return (
    <button
      className={classes}
      disabled={disabled || carregando}
      aria-busy={carregando || undefined}
      {...resto}
    >
      {carregando ? (
        <span className={estilos.spinner} aria-hidden="true" />
      ) : icone ? (
        <span className={estilos.icone}>{icone}</span>
      ) : null}
      {children}
    </button>
  )
}
