import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { aquecerApi } from '../../api/aquecimento'
import { ehSessaoExpirada, mensagemDoErro } from '../../api/erros'
import { useSessao } from '../../auth/contexto'
import { useChat } from '../../chat/contexto'
import { usePessoa } from '../../pessoa/contexto'
import { iniciais, tituloDaConversa } from '../../dominios/texto'
import { Banner } from '../../componentes/Banner'
import { Icone } from '../../componentes/Icone'
import { useOnline } from '../../pwa/usePwa'
import { useVoz } from '../../voz/contexto'
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
  const { api, sair } = useSessao()
  const online = useOnline()

  const { modo: modoVoz, neural, alternar: alternarVoz, definirNeural } = useVoz()
  const [drawerAberto, setDrawerAberto] = useState(false)
  const [erroVozNeural, setErroVozNeural] = useState<string | null>(null)
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
  const rotuloVoz =
    modoVoz === 'so-audio'
      ? 'Só áudio'
      : modoVoz === 'voz'
        ? 'Ouvindo'
        : 'Ouvir'
  const tituloVoz =
    modoVoz === 'so-audio'
      ? 'Só áudio: as respostas são lidas e o texto fica oculto'
      : modoVoz === 'voz'
        ? 'Lendo as respostas em voz alta'
        : 'Ouvir as respostas'
  const titulo = conversaAtual
    ? tituloDaConversa(conversaAtual)
    : conversaId
      ? 'Conversa'
      : 'Nova conversa'

  async function alternarNeural() {
    if (neural) {
      definirNeural(false)
      return
    }
    const aceito = window.confirm(
      'A voz neural tem qualidade melhor, mas envia o texto das respostas ' +
        'para o serviço de voz da Microsoft. Ativar?',
    )
    if (!aceito) return
    try {
      const info = await api.ttsInfo()
      if (!info.disponivel) {
        setErroVozNeural(
          'A voz neural não está disponível neste servidor.',
        )
        return
      }
      setErroVozNeural(null)
      definirNeural(true)
    } catch (falha) {
      if (ehSessaoExpirada(falha)) {
        await sair()
        return
      }
      setErroVozNeural(mensagemDoErro(falha))
    }
  }

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

          <button
            type="button"
            className={`${estilos.botaoVoz} ${
              modoVoz !== 'desligado' ? estilos.botaoVozAtivo : ''
            }`}
            aria-pressed={modoVoz !== 'desligado'}
            aria-label={`Modo de voz: ${tituloVoz}. Toque para alternar.`}
            title={`${tituloVoz} — toque para alternar`}
            onClick={alternarVoz}
          >
            <Icone nome="ouvir" tamanho={18} />
            <span className={estilos.rotuloVoz}>{rotuloVoz}</span>
          </button>

          <button
            type="button"
            className={`${estilos.botaoVoz} ${
              neural ? estilos.botaoVozAtivo : ''
            }`}
            aria-pressed={neural}
            aria-label={
              neural
                ? 'Voz neural ativa. Toque para usar a voz do aparelho.'
                : 'Usar voz neural (envia o texto para o serviço de voz)'
            }
            title={
              neural
                ? 'Voz neural ativa'
                : 'Voz neural: melhor qualidade, envia o texto para o serviço de voz'
            }
            onClick={() => void alternarNeural()}
          >
            <Icone nome="brilho" tamanho={17} />
            <span className={estilos.rotuloVoz}>Neural</span>
          </button>

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

        {erroVozNeural ? (
          <div className={estilos.avisoConexao}>
            <Banner
              tipo="aviso"
              acao={{
                rotulo: 'Fechar',
                aoClicar: () => setErroVozNeural(null),
              }}
            >
              {erroVozNeural}
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
