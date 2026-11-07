import { useEffect, useRef, useState } from 'react'
import { Botao } from '../../componentes/Botao'
import { Icone } from '../../componentes/Icone'
import {
  mensagemDeErroVoz,
  ouvir,
  reconhecimentoSuportado,
  type Ouvinte,
} from '../../voz/ouvir'
import { useInstalacao } from '../../pwa/usePwa'
import {
  consultarPermissaoMicrofone,
  pedirPermissaoMicrofone,
  type EstadoPermissao,
} from '../../voz/permissao'
import estilos from './Conta.module.css'

const ROTULOS: Record<EstadoPermissao, string> = {
  granted: 'Liberado',
  denied: 'Negado',
  prompt: 'Ainda não pedido',
  desconhecido: 'Não verificado',
}

export function SecaoMicrofone() {
  const [estado, setEstado] = useState<EstadoPermissao>('desconhecido')
  const [pedindo, setPedindo] = useState(false)
  const [testando, setTestando] = useState(false)
  const [iniciado, setIniciado] = useState(false)
  const [transcricao, setTranscricao] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const ouvinteRef = useRef<Ouvinte | null>(null)
  const tituloRef = useRef<HTMLHeadingElement>(null)
  const suporta = reconhecimentoSuportado()
  const { ehIOS } = useInstalacao()
  const temMicrofone = typeof navigator !== 'undefined' && 'mediaDevices' in navigator

  useEffect(() => {
    let ativo = true
    void consultarPermissaoMicrofone().then((valor) => {
      if (ativo) setEstado(valor)
    })
    return () => {
      ativo = false
      ouvinteRef.current?.parar()
    }
  }, [])

  useEffect(() => {
    if (window.location.hash !== '#microfone-titulo') return
    const reduzido = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const quadro = window.requestAnimationFrame(() => {
      tituloRef.current?.scrollIntoView({
        behavior: reduzido ? 'auto' : 'smooth',
        block: 'start',
      })
      tituloRef.current?.focus({ preventScroll: true })
    })
    return () => window.cancelAnimationFrame(quadro)
  }, [])

  const permitir = async () => {
    setPedindo(true)
    setErro(null)
    setAviso(null)
    const resultado = await pedirPermissaoMicrofone()
    setPedindo(false)
    if (!resultado.ok) {
      setErro(resultado.erro ?? 'Não foi possível liberar o microfone.')
      setEstado('denied')
      return
    }
    setEstado('granted')
    setAviso('Microfone liberado. Agora use “Testar ditado” ou o microfone do chat.')
  }

  const testar = () => {
    if (testando) {
      ouvinteRef.current?.parar()
      ouvinteRef.current = null
      setTestando(false)
      return
    }
    setErro(null)
    setAviso(null)
    setTranscricao('')
    setIniciado(false)
    setTestando(true)
    const ouvinte = ouvir({
      aoIniciar: () => setIniciado(true),
      aoTexto: (texto) => setTranscricao(texto),
      aoErro: (falha) => {
        setErro(mensagemDeErroVoz(falha))
        setIniciado(false)
        setTestando(false)
      },
      aoFim: () => {
        ouvinteRef.current = null
        setIniciado(false)
        setTestando(false)
      },
    })
    if (!ouvinte) {
      setTestando(false)
      setErro('Reconhecimento de voz indisponível neste navegador.')
      return
    }
    ouvinteRef.current = ouvinte
  }

  return (
    <section className={estilos.secao} aria-labelledby="microfone-titulo">
      <h2
        className={estilos.secaoTitulo}
        id="microfone-titulo"
        ref={tituloRef}
        tabIndex={-1}
      >
        Microfone e voz
      </h2>
      <p className={estilos.secaoTexto}>
        Libere o microfone neste navegador para ditar mensagens no chat. A Sera não
        grava nem guarda o áudio; o navegador pode enviá-lo ao serviço de reconhecimento
        dele.
      </p>

      <div className={estilos.linha}>
        <span className={estilos.rotulo}>Permissão</span>
        <span className={estilos.estado}>
          <span
            className={
              estado === 'granted'
                ? estilos.pontoOk
                : estado === 'denied'
                  ? estilos.pontoFalha
                  : estilos.pontoEspera
            }
            aria-hidden="true"
          />
          {ROTULOS[estado]}
        </span>
      </div>

      {!suporta ? (
        <p className={estilos.secaoTexto}>
          Este navegador não oferece ditado por voz. No iPhone, use o microfone do
          teclado; no Android, use o Chrome atualizado.
        </p>
      ) : null}

      <p className={estilos.secaoTexto}>
        Neste navegador: ditado {suporta ? 'sim' : 'não'} · microfone{' '}
        {temMicrofone ? 'sim' : 'não'} · conexão segura{' '}
        {window.isSecureContext ? 'sim' : 'não'}
      </p>

      {testando ? (
        <p className={estilos.secaoTexto} role="status">
          {iniciado
            ? 'Ouvindo… fale agora. Toque em “Parar teste” quando terminar.'
            : 'Aguardando o microfone e a permissão do navegador…'}
        </p>
      ) : null}

      {erro ? <p className={estilos.secaoTexto}>{erro}</p> : null}
      {aviso ? <p className={estilos.secaoTexto}>{aviso}</p> : null}

      {estado === 'denied' ? (
        <div className={estilos.avisoPermissao}>
          <p className={estilos.secaoTexto}>
            <strong>O navegador está bloqueando o microfone.</strong> Depois de uma
            negativa, o site não consegue pedir a permissão de novo sozinho; ela precisa
            ser liberada nas configurações.
          </p>
          {ehIOS ? (
            <ol className={estilos.passos}>
              <li>
                No Safari, toque em <strong>aA</strong> na barra de endereço →{' '}
                <strong>Ajustes do site</strong> → <strong>Microfone</strong> →{' '}
                <strong>Permitir</strong>.
              </li>
              <li>
                Ou em <strong>Ajustes do iOS → Sera</strong> (ou <strong>Safari</strong>
                ) → <strong>Microfone</strong> e libere.
              </li>
              <li>
                Se a Sera estiver na tela inicial, feche o app e abra de novo; se
                necessário, remova e adicione outra vez.
              </li>
            </ol>
          ) : (
            <ol className={estilos.passos}>
              <li>
                Toque no <strong>cadeado/ícone de ajustes</strong> ao lado do endereço →{' '}
                <strong>Permissões</strong> → <strong>Microfone</strong> →{' '}
                <strong>Permitir</strong>.
              </li>
              <li>
                Ou em{' '}
                <strong>Ajustes do Chrome → Configurações do site → Microfone</strong> e
                permita para este site.
              </li>
              <li>
                Se o Chrome estiver bloqueado no aparelho:{' '}
                <strong>
                  Ajustes do Android → Apps → Chrome → Permissões → Microfone
                </strong>
                .
              </li>
              <li>Recarregue a página e toque em “Tentar de novo”.</li>
            </ol>
          )}
        </div>
      ) : null}
      {transcricao ? (
        <p className={estilos.secaoTexto}>
          <strong>Ouvi:</strong> {transcricao}
        </p>
      ) : null}

      <div className={estilos.acoes}>
        <Botao
          variante={estado === 'granted' ? 'secundario' : 'primario'}
          carregando={pedindo}
          icone={<Icone nome="microfone" tamanho={17} />}
          onClick={() => void permitir()}
        >
          {estado === 'granted'
            ? 'Revalidar microfone'
            : estado === 'denied'
              ? 'Tentar de novo'
              : 'Permitir microfone'}
        </Botao>

        {suporta ? (
          <Botao
            variante="fantasma"
            icone={<Icone nome={testando ? 'parar' : 'ouvir'} tamanho={17} />}
            onClick={testar}
          >
            {testando ? 'Parar teste' : 'Testar ditado'}
          </Botao>
        ) : null}
      </div>
    </section>
  )
}
