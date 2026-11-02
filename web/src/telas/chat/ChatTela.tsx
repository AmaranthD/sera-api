import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { aquecerApi } from '../../api/aquecimento'
import { useSessao } from '../../auth/contexto'
import { useChat } from '../../chat/contexto'
import { usePessoa } from '../../pessoa/contexto'
import { iniciais, tituloDaConversa } from '../../dominios/texto'
import { Banner } from '../../componentes/Banner'
import { Icone } from '../../componentes/Icone'
import { useOnline } from '../../pwa/usePwa'
import { AvisoAcordando } from './AvisoAcordando'
import { Composer } from './Composer'
import { ConteudoLateral } from './ConteudoLateral'
import { DrawerConversas } from './DrawerConversas'
import { FundoPaladina } from './FundoPaladina'
import { PainelConversa } from './PainelConversa'
import estilos from './Chat.module.css'

export function ChatTela() {
  const {
    conversaId,
    conversaAtual,
    status,
    erro,
    podeReenviar,
    enviar,
    parar,
    reenviar,
    recarregarConversa,
    limparErro,
  } = useChat()
  const { pessoa } = usePessoa()
  const { api } = useSessao()
  const online = useOnline()

  const [drawerAberto, setDrawerAberto] = useState(false)
  const [rascunho, setRascunho] = useState('')
  const [modoJw, setModoJw] = useState(false)

  useEffect(() => {
    const aoVoltar = () => {
      if (document.visibilityState === 'visible') void aquecerApi(api)
    }
    document.addEventListener('visibilitychange', aoVoltar)
    return () => document.removeEventListener('visibilitychange', aoVoltar)
  }, [api])

  const ocupado = status === 'enviando' || status === 'transmitindo'
  const titulo = conversaAtual
    ? tituloDaConversa(conversaAtual)
    : conversaId
      ? 'Conversa'
      : 'Nova conversa'

  const enviarTexto = (texto: string) => {
    if (!online || ocupado) return
    setRascunho('')
    void enviar(texto, modoJw ? { fonte: 'jw' } : undefined)
  }

  const sugerir = (texto: string) => {
    setRascunho(texto)
    window.requestAnimationFrame(() => {
      const campo = document.getElementById('campo-mensagem')
      if (campo instanceof HTMLTextAreaElement) campo.focus()
    })
  }

  const acaoDoErro = podeReenviar
    ? { rotulo: 'Tentar de novo', aoClicar: reenviar }
    : conversaId
      ? {
          rotulo: 'Recarregar',
          aoClicar: () => {
            limparErro()
            void recarregarConversa()
          },
        }
      : undefined

  return (
    <div className={estilos.app}>
      <a className="pularParaConteudo" href="#conteudo">
        Pular para a conversa
      </a>

      <aside className={estilos.sidebar}>
        <ConteudoLateral />
      </aside>

      <main className={estilos.principal} id="conteudo">
        <FundoPaladina />
        <header className={estilos.cabecalho}>
          <button
            type="button"
            className={`${estilos.botaoIcone} ${estilos.menuMobile}`}
            aria-label="Abrir conversas"
            aria-expanded={drawerAberto}
            onClick={() => setDrawerAberto(true)}
          >
            <Icone nome="menu" />
          </button>

          <div className={estilos.cabecalhoTexto}>
            <h1 className={estilos.cabecalhoTitulo}>{titulo}</h1>
            <p className={estilos.cabecalhoSub}>com Sera</p>
          </div>

          <Link
            to="/agenda"
            className={estilos.botaoIcone}
            aria-label="Abrir agenda"
            title="Agenda"
          >
            <Icone nome="relogio" />
          </Link>

          {pessoa ? (
            <Link
              to="/conta"
              className={`${estilos.avatar} ${estilos.avatarLink}`}
              aria-label="Conta e ajustes"
            >
              {iniciais(pessoa.nome)}
            </Link>
          ) : null}
        </header>

        {!online ? (
          <div className={estilos.avisoConexao}>
            <Banner tipo="aviso">
              <span className={estilos.textoOffline}>
                <Icone nome="offline" tamanho={16} />
                Sem conexão. Você pode ler o que já está aberto, mas não enviar
                mensagens.
              </span>
            </Banner>
          </div>
        ) : null}

        {erro && online ? (
          <div className={estilos.avisoConexao}>
            <Banner tipo="erro" acao={acaoDoErro}>
              {erro}
            </Banner>
          </div>
        ) : null}

        <PainelConversa key={conversaId ?? 'nova'} aoSugerir={sugerir} />

        <Composer
          valor={rascunho}
          aoMudar={setRascunho}
          aoEnviar={enviarTexto}
          aoParar={parar}
          ocupado={ocupado}
          online={online}
          modoJw={modoJw}
          aoAlternarJw={() => setModoJw((atual) => !atual)}
          aviso={<AvisoAcordando ativo={status === 'enviando'} />}
        />
      </main>

      <DrawerConversas aberto={drawerAberto} aoFechar={() => setDrawerAberto(false)} />
    </div>
  )
}
