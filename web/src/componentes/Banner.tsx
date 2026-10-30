import type { ReactNode } from 'react'
import { Icone } from './Icone'
import estilos from './Banner.module.css'

interface Props {
  tipo?: 'erro' | 'info' | 'aviso' | 'sucesso'
  children: ReactNode
  acao?: { rotulo: string; aoClicar: () => void }
  className?: string
}

export function Banner({ tipo = 'info', children, acao, className }: Props) {
  const classes = [estilos.banner, estilos[tipo], className].filter(Boolean).join(' ')
  return (
    <div className={classes} role={tipo === 'erro' ? 'alert' : 'status'}>
      <span className={estilos.icone} aria-hidden="true">
        <Icone nome={tipo === 'erro' || tipo === 'aviso' ? 'alerta' : 'escudo'} />
      </span>
      <div className={estilos.conteudo}>{children}</div>
      {acao ? (
        <button type="button" className={estilos.acao} onClick={acao.aoClicar}>
          {acao.rotulo}
        </button>
      ) : null}
    </div>
  )
}
