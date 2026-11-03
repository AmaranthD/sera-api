import { useEffect, useRef, useState, type ReactNode } from 'react'
import { LIMITE_MENSAGEM } from '../../dominios/texto'
import { Icone } from '../../componentes/Icone'
import {
  confirmarUsoDaVoz,
  mensagemDeErroVoz,
  ouvir,
  reconhecimentoSuportado,
  type Ouvinte,
} from '../../voz/ouvir'
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
  const [ouvindo, setOuvindo] = useState(false)
  const [erroVoz, setErroVoz] = useState<string | null>(null)
  const [avisoDitado, setAvisoDitado] = useState<string | null>(null)
  const ouvinteRef = useRef<Ouvinte | null>(null)
  const baseRef = useRef('')
  const finalRef = useRef('')
  const teveTextoRef = useRef(false)
  const suportaVoz = reconhecimentoSuportado()

  useEffect(() => {
    const campo = referencia.current
    if (!campo) return
    campo.style.height = 'auto'
    campo.style.height = `${Math.min(campo.scrollHeight, 180)}px`
  }, [valor])

  useEffect(() => () => ouvinteRef.current?.parar(), [])

  const pararDitado = () => {
    ouvinteRef.current?.parar()
    ouvinteRef.current = null
    setOuvindo(false)
  }

  const alternarDitado = () => {
    if (ouvindo) {
      pararDitado()
      return
    }
    if (!online || ocupado) return
    if (!confirmarUsoDaVoz()) return

    setErroVoz(null)
    setAvisoDitado(null)
    baseRef.current = valor.trim()
    finalRef.current = ''
    teveTextoRef.current = false
    const ouvinte = ouvir({
      aoTexto: (texto, final) => {
        teveTextoRef.current = true
        if (final) finalRef.current = `${finalRef.current} ${texto}`.trim()
        const partes = [baseRef.current, finalRef.current]
        if (!final) partes.push(texto)
        aoMudar(partes.filter(Boolean).join(' '))
      },
      aoErro: (erro) => {
        setErroVoz(mensagemDeErroVoz(erro))
        ouvinteRef.current = null
        setOuvindo(false)
      },
      aoFim: () => {
        ouvinteRef.current = null
        setOuvindo(false)
        setAvisoDitado(
          teveTextoRef.current
            ? 'Ditado pronto — revise e toque em enviar.'
            : 'Não ouvi nada. Tente de novo.',
        )
      },
    })
    if (!ouvinte) {
      setErroVoz('Reconhecimento de voz indisponível neste navegador.')
      return
    }
    ouvinteRef.current = ouvinte
    setOuvindo(true)
  }

  const podeEnviar = online && !ocupado && valor.trim().length > 0

  const enviar = () => {
    if (!podeEnviar) return
    if (ouvindo) pararDitado()
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
            ouvindo
              ? 'Ouvindo… fale agora'
              : !online
                ? 'Sem conexão. Sua mensagem fica aqui.'
                : modoJw
                  ? 'Pergunte sobre a Bíblia ou publicações JW…'
                  : 'Escreva para a Sera…'
          }
          value={valor}
          disabled={!online || ocupado}
          onChange={(evento) => {
            if (!ouvindo) setAvisoDitado(null)
            aoMudar(evento.target.value)
          }}
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
        {suportaVoz ? (
          <button
            type="button"
            className={`${estilos.microfone} ${
              ouvindo ? estilos.microfoneAtivo : ''
            }`}
            aria-pressed={ouvindo}
            aria-label={ouvindo ? 'Parar ditado' : 'Ditar mensagem'}
            title={
              ouvindo
                ? 'Parar ditado'
                : 'Ditar mensagem (o áudio pode ir para o serviço do navegador)'
            }
            disabled={!online || ocupado}
            onClick={alternarDitado}
          >
            <Icone nome={ouvindo ? 'parar' : 'microfone'} tamanho={18} />
          </button>
        ) : null}
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
        <span role={erroVoz ? 'status' : undefined}>
          {erroVoz ??
            avisoDitado ??
            (!online
              ? 'Sem conexão para enviar.'
              : modoJw
                ? 'Modo JW · só Bíblia e publicações JW'
                : 'Enter envia · Shift + Enter quebra a linha')}
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
