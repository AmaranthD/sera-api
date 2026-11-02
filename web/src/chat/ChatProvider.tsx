import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ehSessaoExpirada, ErroApi, mensagemDoErro } from '../api/erros'
import { aquecerApi } from '../api/aquecimento'
import type { Conversa, Mensagem } from '../dominios/tipos'
import { normalizarMensagem } from '../dominios/texto'
import { useSessao } from '../auth/contexto'
import { usePessoa } from '../pessoa/contexto'
import { ChatContext, type StatusChat } from './contexto'

const INTERVALO_POLL_MS = 900
const LIMITE_JOB_MS = 5 * 60 * 1000

let contadorLocal = 0

function idLocal(): string {
  contadorLocal += 1
  return `local-${Date.now()}-${contadorLocal}`
}

function idDaRota(pathname: string): string | null {
  const encontrado = /^\/c\/([^/]+)\/?$/.exec(pathname)
  if (!encontrado?.[1]) return null
  try {
    return decodeURIComponent(encontrado[1])
  } catch {
    return null
  }
}

interface JobAtivo {
  conversaId: string
  respostaId: string
}

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const { api, sair } = useSessao()
  const { pessoa } = usePessoa()
  const localizacao = useLocation()
  const navegar = useNavigate()

  const [conversas, setConversas] = useState<Conversa[]>([])
  const [conversaId, setConversaId] = useState<string | null>(null)
  const [mensagens, setMensagens] = useState<Mensagem[]>([])
  const [status, setStatus] = useState<StatusChat>('ocioso')
  const [erro, setErro] = useState<string | null>(null)
  const [carregandoConversas, setCarregandoConversas] = useState(false)
  const [carregandoMensagens, setCarregandoMensagens] = useState(false)
  const [textoParaReenviar, setTextoParaReenviar] = useState<string | null>(null)
  const [jobAtivo, setJobAtivo] = useState<JobAtivo | null>(null)
  const [gatilhoPoll, setGatilhoPoll] = useState(0)

  const conversaIdRef = useRef<string | null>(null)
  const statusRef = useRef<StatusChat>('ocioso')
  const montadoRef = useRef(true)
  const inicioJobRef = useRef(0)
  const textoEnviadoRef = useRef('')
  const enviandoRef = useRef(false)
  const cancelarPedidoRef = useRef(false)

  const mudarStatus = useCallback((novo: StatusChat) => {
    statusRef.current = novo
    setStatus(novo)
  }, [])

  const carregarConversas = useCallback(async () => {
    if (!pessoa) return
    setCarregandoConversas(true)
    try {
      const lista = await api.listarConversas(pessoa.id)
      if (!montadoRef.current) return
      setConversas(lista)
    } catch (falha) {
      if (ehSessaoExpirada(falha)) {
        await sair()
      } else if (montadoRef.current) {
        setErro(mensagemDoErro(falha))
      }
    } finally {
      if (montadoRef.current) setCarregandoConversas(false)
    }
  }, [api, pessoa, sair])

  useEffect(() => {
    void carregarConversas()
  }, [carregarConversas])

  const carregarMensagens = useCallback(
    async (id: string) => {
      setCarregandoMensagens(true)
      setErro(null)
      try {
        const lista = await api.listarMensagens(id)
        if (conversaIdRef.current !== id) return
        setMensagens(lista)

        const gerando = [...lista]
          .reverse()
          .find(
            (mensagem) =>
              mensagem.papel === 'assistant' && mensagem.status === 'gerando',
          )
        if (gerando) {
          inicioJobRef.current = Date.now()
          setJobAtivo({ conversaId: id, respostaId: gerando.id })
          mudarStatus('transmitindo')
        } else {
          setJobAtivo(null)
          mudarStatus('ocioso')
        }
      } catch (falha) {
        if (ehSessaoExpirada(falha)) {
          await sair()
          return
        }
        if (conversaIdRef.current !== id) return
        setMensagens([])
        setErro(mensagemDoErro(falha))
      } finally {
        if (conversaIdRef.current === id) {
          setCarregandoMensagens(false)
        }
      }
    },
    [api, mudarStatus, sair],
  )

  // A URL é a fonte da verdade da conversa aberta; o provider sobrevive à
  // troca de rota e o job continua no servidor.
  useEffect(() => {
    const id = idDaRota(localizacao.pathname)
    if (id === conversaIdRef.current) return

    setJobAtivo(null)
    conversaIdRef.current = id
    setConversaId(id)
    setErro(null)
    setTextoParaReenviar(null)
    mudarStatus('ocioso')
    if (id) {
      void carregarMensagens(id)
    } else {
      setMensagens([])
      setCarregandoMensagens(false)
    }
  }, [localizacao.pathname, carregarMensagens, mudarStatus])

  useEffect(() => {
    montadoRef.current = true
    return () => {
      montadoRef.current = false
    }
  }, [])

  // Ao voltar do segundo plano, consulta o job imediatamente.
  useEffect(() => {
    const aoVoltar = () => {
      if (document.visibilityState === 'visible' && jobAtivo) {
        setGatilhoPoll((valor) => valor + 1)
      }
    }
    document.addEventListener('visibilitychange', aoVoltar)
    return () => document.removeEventListener('visibilitychange', aoVoltar)
  }, [jobAtivo])

  // Polling: o servidor gera a resposta; aqui só acompanhamos o andamento.
  useEffect(() => {
    if (!jobAtivo) return
    let cancelado = false
    let temporizador: number | null = null
    const { conversaId: idConversa, respostaId } = jobAtivo

    if (statusRef.current !== 'transmitindo') mudarStatus('transmitindo')

    const consultar = async () => {
      try {
        const resposta = await api.estadoChat(respostaId)
        if (cancelado || !montadoRef.current) return
        if (conversaIdRef.current !== idConversa) return

        setMensagens((atuais) =>
          atuais.map((mensagem) =>
            mensagem.id === respostaId ? { ...mensagem, ...resposta } : mensagem,
          ),
        )

        if (resposta.status === 'gerando') {
          if (Date.now() - inicioJobRef.current > LIMITE_JOB_MS) {
            setJobAtivo(null)
            setErro('A resposta demorou demais. Tente de novo.')
            setTextoParaReenviar(textoEnviadoRef.current || null)
            mudarStatus('erro')
            return
          }
          temporizador = window.setTimeout(() => {
            void consultar()
          }, INTERVALO_POLL_MS)
          return
        }

        // Terminou: recarrega a conversa para alinhar ids, fontes e histórico.
        const lista = await api.listarMensagens(idConversa)
        if (cancelado || !montadoRef.current) return
        if (conversaIdRef.current !== idConversa) return
        setMensagens(lista)

        setJobAtivo(null)
        setTextoParaReenviar(null)
        if (resposta.status === 'erro') {
          const indice = lista.findIndex((mensagem) => mensagem.id === respostaId)
          const anterior = indice > 0 ? lista[indice - 1] : null
          setTextoParaReenviar(anterior?.papel === 'user' ? anterior.conteudo : null)
          setErro('A Sera não conseguiu concluir. Tente de novo.')
          mudarStatus('erro')
        } else {
          mudarStatus('ocioso')
        }
        void carregarConversas()
      } catch (falha) {
        if (cancelado || !montadoRef.current) return
        if (ehSessaoExpirada(falha)) {
          await sair()
          return
        }
        setJobAtivo(null)
        if (falha instanceof ErroApi && falha.status === 404) {
          setErro('Não encontramos a resposta desta conversa.')
        } else {
          setErro(mensagemDoErro(falha))
        }
        setTextoParaReenviar(textoEnviadoRef.current || null)
        mudarStatus('erro')
      }
    }

    void consultar()
    return () => {
      cancelado = true
      if (temporizador !== null) window.clearTimeout(temporizador)
    }
  }, [jobAtivo, gatilhoPoll, api, carregarConversas, mudarStatus, sair])

  const enviar = useCallback(
    async (bruto: string, opcoes?: { fonte?: 'jw' }) => {
      if (enviandoRef.current || statusRef.current === 'transmitindo') {
        return
      }
      const texto = normalizarMensagem(bruto)
      if (!texto) return

      enviandoRef.current = true
      cancelarPedidoRef.current = false
      const fonte = opcoes?.fonte
      const idConversa = conversaIdRef.current
      const agora = new Date().toISOString()
      const idUsuario = idLocal()
      const idAssistente = idLocal()
      textoEnviadoRef.current = texto

      setMensagens((atuais) => [
        ...atuais,
        {
          id: idUsuario,
          conversa_id: idConversa ?? undefined,
          papel: 'user',
          conteudo: texto,
          status: 'completa',
          criada_em: agora,
        },
        {
          id: idAssistente,
          conversa_id: idConversa ?? undefined,
          papel: 'assistant',
          conteudo: '',
          status: 'gerando',
          criada_em: agora,
        },
      ])
      setErro(null)
      setTextoParaReenviar(null)
      mudarStatus('enviando')

      try {
        const trabalho = await api.iniciarChat({
          mensagem: texto,
          conversaId: idConversa ?? undefined,
          fonte,
        })

        conversaIdRef.current = trabalho.conversa_id
        setConversaId(trabalho.conversa_id)
        setMensagens((atuais) =>
          atuais.map((mensagem) => {
            if (mensagem.id === idUsuario) {
              return {
                ...mensagem,
                id: trabalho.mensagem_id,
                conversa_id: trabalho.conversa_id,
              }
            }
            if (mensagem.id === idAssistente) {
              return {
                ...mensagem,
                id: trabalho.resposta_id,
                conversa_id: trabalho.conversa_id,
              }
            }
            return mensagem
          }),
        )

        if (idDaRota(window.location.pathname) !== trabalho.conversa_id) {
          navegar(`/c/${trabalho.conversa_id}`, { replace: true })
        }
        if (!idConversa) {
          void carregarConversas()
        }

        if (cancelarPedidoRef.current) {
          cancelarPedidoRef.current = false
          await api.cancelarChat(trabalho.resposta_id).catch(() => undefined)
          if (!montadoRef.current) return
          mudarStatus('ocioso')
          void carregarMensagens(trabalho.conversa_id)
          return
        }

        inicioJobRef.current = Date.now()
        mudarStatus('transmitindo')
        setJobAtivo({
          conversaId: trabalho.conversa_id,
          respostaId: trabalho.resposta_id,
        })
      } catch (falha) {
        if (ehSessaoExpirada(falha)) {
          await sair()
          return
        }
        if (!montadoRef.current) return
        setMensagens((atuais) =>
          atuais.map((mensagem) => {
            if (mensagem.id === idUsuario || mensagem.id === idAssistente) {
              return { ...mensagem, status: 'erro' }
            }
            return mensagem
          }),
        )
        setErro(mensagemDoErro(falha))
        setTextoParaReenviar(texto)
        mudarStatus('erro')
      } finally {
        enviandoRef.current = false
      }
    },
    [api, carregarConversas, carregarMensagens, mudarStatus, navegar, sair],
  )

  const parar = useCallback(() => {
    if (enviandoRef.current && !jobAtivo) {
      // O POST ainda não voltou: pede o cancelamento assim que o job existir.
      cancelarPedidoRef.current = true
      mudarStatus('ocioso')
      return
    }
    const ativo = jobAtivo
    setJobAtivo(null)
    setTextoParaReenviar(null)
    mudarStatus('ocioso')
    if (!ativo) return
    void api
      .cancelarChat(ativo.respostaId)
      .catch(() => undefined)
      .finally(() => {
        if (montadoRef.current && conversaIdRef.current === ativo.conversaId) {
          void carregarMensagens(ativo.conversaId)
        }
      })
  }, [api, carregarMensagens, jobAtivo, mudarStatus])

  const reenviar = useCallback(() => {
    if (!textoParaReenviar) return
    const texto = textoParaReenviar
    setTextoParaReenviar(null)
    setMensagens((atuais) => atuais.filter((mensagem) => mensagem.status !== 'erro'))
    setErro(null)
    void enviar(texto)
  }, [enviar, textoParaReenviar])

  const novaConversa = useCallback(() => {
    setJobAtivo(null)
    conversaIdRef.current = null
    setConversaId(null)
    setMensagens([])
    setErro(null)
    setTextoParaReenviar(null)
    mudarStatus('ocioso')
    void aquecerApi(api)
    navegar('/')
  }, [api, mudarStatus, navegar])

  const selecionarConversa = useCallback(
    (id: string) => {
      if (id === conversaIdRef.current) return
      navegar(`/c/${id}`)
    },
    [navegar],
  )

  const limparErro = useCallback(() => setErro(null), [])

  const recarregarConversa = useCallback(async () => {
    const id = conversaIdRef.current
    if (id) await carregarMensagens(id)
  }, [carregarMensagens])

  const conversaAtual = useMemo(
    () => conversas.find((conversa) => conversa.id === conversaId) ?? null,
    [conversas, conversaId],
  )

  const valor = useMemo(
    () => ({
      conversas,
      conversaId,
      conversaAtual,
      mensagens,
      status,
      erro,
      carregandoConversas,
      carregandoMensagens,
      podeReenviar: Boolean(textoParaReenviar),
      enviar,
      parar,
      reenviar,
      novaConversa,
      selecionarConversa,
      recarregarConversas: carregarConversas,
      recarregarConversa,
      limparErro,
    }),
    [
      conversas,
      conversaId,
      conversaAtual,
      mensagens,
      status,
      erro,
      carregandoConversas,
      carregandoMensagens,
      textoParaReenviar,
      enviar,
      parar,
      reenviar,
      novaConversa,
      selecionarConversa,
      carregarConversas,
      recarregarConversa,
      limparErro,
    ],
  )

  return <ChatContext.Provider value={valor}>{children}</ChatContext.Provider>
}
