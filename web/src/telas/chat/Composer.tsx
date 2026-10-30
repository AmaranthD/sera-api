import { useEffect, useRef, type ReactNode } from 'react'
import { LIMITE_MENSAGEM } from '../../dominios/texto'
import { Icone } from '../../componentes/Icone'
import estilos from './Chat.module.css'

interface Props {
  valor: string
  aoMudar: (valor: string) => void
  aoEnviar: (texto: string) => void
  aoParar: () => void
  ocupado: boolean
  online: boolean
  aviso?: ReactNode
}

export function Composer({
  valor,
  aoMudar,
  aoEnviar,
  aoParar,
  ocupado,
  online,
  aviso,
}: Props) {
  const referencia = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const campo = referencia.current
    if (!campo) return
    campo.style.height = 'auto'
    campo.style.height = `${Math.min(campo.scrollHeight, 180)}px`
  }, [valor])

  const podeEnviar = online && !ocupado && valor.trim().length > 0

  const enviar = () => {
    if (!podeEnviar) return
    aoEnviar(valor)
  }

  return (
    <div className={estilos.composerArea}>
      {aviso}
      <form
        className={estilos.composer}
        onSubmit={(evento) => {
          evento.preventDefault()
          enviar()
        }}
      >
        <label className="srOnly" htmlFor="campo-mensagem">
          Escreva sua mensagem para a Sera
        </label>
        <textarea
          id="campo-mensagem"
          ref={referencia}
          className={estilos.textarea}
          rows={1}
          maxLength={LIMITE_MENSAGEM}
          placeholder={
            online ? 'Escreva para a Sera…' : 'Sem conexão. Sua mensagem fica aqui.'
          }
          value={valor}
          disabled={!online || ocupado}
          onChange={(evento) => aoMudar(evento.target.value)}
          onKeyDown={(evento) => {
            if (
              evento.key === 'Enter' &&
              !evento.shiftKey &&
              !evento.nativeEvent.isComposing
            ) {
              evento.preventDefault()
              enviar()
            }
          }}
        />
        {ocupado ? (
          <button
            type="button"
            className={`${estilos.enviar} ${estilos.parar}`}
            onClick={aoParar}
            aria-label="Parar a resposta"
            title="Parar a resposta"
          >
            <Icone nome="parar" tamanho={18} />
          </button>
        ) : (
          <button
            type="submit"
            className={estilos.enviar}
            disabled={!podeEnviar}
            aria-label="Enviar mensagem"
            title="Enviar mensagem"
          >
            <Icone nome="enviar" tamanho={19} />
          </button>
        )}
      </form>
      <div className={estilos.composerRodape}>
        <span>
          {online
            ? 'Enter envia · Shift + Enter quebra a linha'
            : 'Sem conexão para enviar.'}
        </span>
        {valor.length > 7000 ? (
          <span className={estilos.contador}>
            {valor.length}/{LIMITE_MENSAGEM}
          </span>
        ) : null}
      </div>
    </div>
  )
}
