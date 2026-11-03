import { useEffect, useRef, useState, type ReactNode } from 'react'
import { LIMITE_MENSAGEM } from '../../dominios/texto'
import { Icone } from '../../componentes/Icone'
import {
  mensagemDeErroVoz,
  ouvir,
  reconhecimentoSuportado,
  registrarConsentimentoVoz,
  temConsentimentoVoz,
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
  const [pedirConsentimento, setPedirConsentimento] = useState(false)
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

  const iniciarDitado = () => {
    if (!window.isSecureContext) {
      setErroVoz('O microfone exige uma conexão segura (HTTPS).')
      return
    }

    setErroVoz(null)
    setAvisoDitado(null)
    baseRef.current = valor.trim()
    finalRef.current = ''
    teveTextoRef.current = false
    setOuvindo(true)
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
      setOuvindo(false)
      setErroVoz('Reconhecimento de voz indisponível neste navegador.')
      return
    }
    ouvinteRef.current = ouvinte
  }

  const alternarDitado = () => {
    if (ouvindo) {
      pararDitado()
      return
    }
    if (!online) {
      setErroVoz('Sem conexão para usar o microfone.')
      return
    }
    if (ocupado) {
      setErroVoz('Espere a resposta terminar para ditar.')
      return
    }
    if (!temConsentimentoVoz()) {
      setPedirConsentimento(true)
      return
    }
    iniciarDitado()
  }

  const permitirVoz = () => {
    registrarConsentimentoVoz()
    setPedirConsentimento(false)
    iniciarDitado()
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
      {erroVoz ? (
        <div className={estilos.erroVoz} role="alert">
          <span>{erroVoz}</span>
          <button
            type="button"
            className={estilos.fecharErroVoz}
            aria-label="Fechar aviso de voz"
            onClick={() => setErroVoz(null)}
          >
            ×
          </button>
        </div>
      ) : null}
      {!suportaVoz ? (
        <p className={estilos.vozIndisponivel}>
          Ditado não disponível neste navegador. No iPhone, use o microfone do
          teclado; no Android, use Chrome atualizado.
        </p>
      ) : null}
      {pedirConsentimento ? (
        <div
          className={estilos.consentimentoVoz}
          role="dialog"
          aria-label="Permissão para usar o microfone"
        >
          <p>
            Para ditar, o navegador vai ouvir o microfone e pode enviar o
            áudio para o serviço dele. A Sera não grava nem guarda áudio.
          </p>
          <div className={estilos.consentimentoAcoes}>
            <button
              type="button"
              className={estilos.consentimentoPermitir}
              onClick={permitirVoz}
            >
              Permitir
            </button>
            <button
              type="button"
              className={estilos.consentimentoCancelar}
              onClick={() => setPedirConsentimento(false)}
            >
              Cancelar
            </button>
          </div>
        </div>
      ) : null}
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
            <span className={estilos.rotuloMicrofone}>Ditar</span>
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
          {avisoDitado ??
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
