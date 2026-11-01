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
  modoJw: boolean
  aoAlternarJw: () => void
  aviso?: ReactNode
}

export function Composer({
  valor,
  aoMudar,
  aoEnviar,
  aoParar,
  ocupado,
  online,
  modoJw,
  aoAlternarJw,
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
            !online
              ? 'Sem conexão. Sua mensagem fica aqui.'
              : modoJw
                ? 'Pergunte sobre a Bíblia ou publicações JW…'
                : 'Escreva para a Sera…'
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
        <button
          type="button"
          className={`${estilos.modoJw} ${modoJw ? estilos.modoJwAtivo : ''}`}
          aria-pressed={modoJw}
          aria-label={modoJw ? 'Desativar modo JW' : 'Ativar modo JW'}
          title={
            modoJw
              ? 'Modo JW ativo: a resposta usa só Bíblia e publicações JW'
              : 'Modo JW: a resposta usa só Bíblia e publicações JW'
          }
          disabled={!online || ocupado}
          onClick={aoAlternarJw}
        >
          JW
        </button>
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
          {!online
            ? 'Sem conexão para enviar.'
            : modoJw
              ? 'Modo JW · só Bíblia e publicações JW'
              : 'Enter envia · Shift + Enter quebra a linha'}
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
