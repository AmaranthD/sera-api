import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ehSessaoExpirada, mensagemDoErro } from '../api/erros'
import { aquecerApi } from '../api/aquecimento'
import type { Conversa, Fonte, Mensagem } from '../dominios/tipos'
import { normalizarMensagem } from '../dominios/texto'
import { useSessao } from '../auth/contexto'
import { usePessoa } from '../pessoa/contexto'
import { ChatContext, type StatusChat } from './contexto'

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

interface FluxoAtivo {
  conversaId: string | null
  mensagemUsuarioId: string
  mensagemAssistenteId: string
  partes: string
  fontes: Fonte[]
  controller: AbortController
  motivoAborto: 'usuario' | 'limite' | null
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

  const conversaIdRef = useRef<string | null>(null)
  const statusRef = useRef<StatusChat>('ocioso')
  const montadoRef = useRef(true)
  const textoEnviadoRef = useRef('')
  const enviandoRef = useRef(false)
  const fluxoRef = useRef<FluxoAtivo | null>(null)

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

        const fluxo = fluxoRef.current
        if (fluxo?.conversaId === id) {
          setMensagens([
            ...lista,
            {
              id: fluxo.mensagemAssistenteId,
              conversa_id: id,
              papel: 'assistant',
              conteudo: fluxo.partes,
              status: 'gerando',
              criada_em: new Date().toISOString(),
              fontes: fluxo.fontes,
            },
          ])
          mudarStatus('transmitindo')
        } else {
          setMensagens(lista)
          const gerando = [...lista]
            .reverse()
            .find(
              (mensagem) =>
                mensagem.papel === 'assistant' && mensagem.status === 'gerando',
            )
          mudarStatus(
            fluxoRef.current || gerando ? 'transmitindo' : 'ocioso',
          )
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
  // troca de rota e o stream continua mesmo quando a conversa sai da tela.
  useEffect(() => {
    const id = idDaRota(localizacao.pathname)
    if (id === conversaIdRef.current) return

    conversaIdRef.current = id
    setConversaId(id)
    setErro(null)
    setTextoParaReenviar(null)
    const fluxo = fluxoRef.current
    mudarStatus(fluxo ? 'transmitindo' : 'ocioso')
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

  const enviar = useCallback(
    async (bruto: string, opcoes?: { fonte?: 'jw' }) => {
      if (
        enviandoRef.current ||
        fluxoRef.current ||
        statusRef.current === 'transmitindo'
      ) {
        return
      }
      const texto = normalizarMensagem(bruto)
      if (!texto) return

      enviandoRef.current = true
      const fonte = opcoes?.fonte
      const idConversa = conversaIdRef.current
      const agora = new Date().toISOString()
      const idUsuario = idLocal()
      const idAssistente = idLocal()
      textoEnviadoRef.current = texto

      const fluxo: FluxoAtivo = {
        conversaId: idConversa,
        mensagemUsuarioId: idUsuario,
        mensagemAssistenteId: idAssistente,
        partes: '',
        fontes: [],
        controller: new AbortController(),
        motivoAborto: null,
      }
      fluxoRef.current = fluxo

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

      const limite = window.setTimeout(() => {
        fluxo.motivoAborto = 'limite'
        fluxo.controller.abort()
      }, LIMITE_JOB_MS)

      try {
        await api.transmitirChat(
          { mensagem: texto, conversaId: idConversa ?? undefined, fonte },
          (evento) => {
            if (evento.tipo === 'start') {
              fluxo.conversaId = evento.conversaId
              fluxo.mensagemUsuarioId = evento.mensagemId
              // Se o usuário trocou de conversa enquanto o POST voltava,
              // não o puxa de volta: o stream continua em segundo plano.
              if (conversaIdRef.current !== idConversa) return
              conversaIdRef.current = evento.conversaId
              setConversaId(evento.conversaId)
              setMensagens((atuais) =>
                atuais.map((mensagem) => {
                  if (mensagem.id === idUsuario) {
                    return {
                      ...mensagem,
                      id: evento.mensagemId,
                      conversa_id: evento.conversaId,
                    }
                  }
                  if (mensagem.id === idAssistente) {
                    return { ...mensagem, conversa_id: evento.conversaId }
                  }
                  return mensagem
                }),
              )
              if (idDaRota(window.location.pathname) !== evento.conversaId) {
                navegar(`/c/${evento.conversaId}`, { replace: true })
              }
              if (!idConversa) {
                void carregarConversas()
              }
              mudarStatus('transmitindo')
              return
            }

            if (evento.tipo === 'token') {
              fluxo.partes += evento.texto
              if (conversaIdRef.current === fluxo.conversaId) {
                setMensagens((atuais) =>
                  atuais.map((mensagem) =>
                    mensagem.id === fluxo.mensagemAssistenteId
                      ? { ...mensagem, conteudo: fluxo.partes }
                      : mensagem,
                  ),
                )
              }
              return
            }

            if (evento.tipo === 'sources') {
              fluxo.fontes = evento.fontes
              if (conversaIdRef.current === fluxo.conversaId) {
                setMensagens((atuais) =>
                  atuais.map((mensagem) =>
                    mensagem.id === fluxo.mensagemAssistenteId
                      ? { ...mensagem, fontes: evento.fontes }
                      : mensagem,
                  ),
                )
              }
              return
            }

            if (evento.tipo === 'done') {
              fluxo.mensagemAssistenteId = evento.mensagemId
              fluxoRef.current = null
              if (conversaIdRef.current === fluxo.conversaId) {
                setMensagens((atuais) =>
                  atuais.map((mensagem) =>
                    mensagem.id === idAssistente
                      ? {
                          ...mensagem,
                          id: evento.mensagemId,
                          conteudo: fluxo.partes,
                          status: 'completa',
                        }
                      : mensagem,
                  ),
                )
                mudarStatus('ocioso')
                void carregarMensagens(evento.conversaId)
              }
              void carregarConversas()
              return
            }

            fluxo.motivoAborto = 'usuario'
            fluxoRef.current = null
            if (conversaIdRef.current === fluxo.conversaId) {
              setMensagens((atuais) =>
                atuais.map((mensagem) =>
                  mensagem.id === idAssistente
                    ? { ...mensagem, status: 'erro' }
                    : mensagem,
                ),
              )
              setErro(
                evento.detalhe || 'A Sera não conseguiu concluir. Tente de novo.',
              )
              setTextoParaReenviar(texto)
              mudarStatus('erro')
            }
          },
          fluxo.controller.signal,
        )
      } catch (falha) {
        if (fluxo.motivoAborto === 'usuario') return
        if (ehSessaoExpirada(falha)) {
          await sair()
          return
        }
        if (!montadoRef.current) return
        if (fluxo.motivoAborto === 'limite') {
          setErro('A resposta demorou demais. Tente de novo.')
        } else {
          setErro(mensagemDoErro(falha))
        }
        setMensagens((atuais) =>
          atuais.map((mensagem) => {
            if (mensagem.id === idUsuario || mensagem.id === idAssistente) {
              return { ...mensagem, status: 'erro' }
            }
            return mensagem
          }),
        )
        setTextoParaReenviar(texto)
        mudarStatus('erro')
      } finally {
        window.clearTimeout(limite)
        enviandoRef.current = false
        if (fluxoRef.current === fluxo) fluxoRef.current = null
      }
    },
    [
      api,
      carregarConversas,
      carregarMensagens,
      mudarStatus,
      navegar,
      sair,
    ],
  )

  const parar = useCallback(() => {
    const fluxo = fluxoRef.current
    if (!fluxo) {
      mudarStatus('ocioso')
      return
    }
    fluxo.motivoAborto = 'usuario'
    fluxo.controller.abort()
    fluxoRef.current = null
    setTextoParaReenviar(null)
    mudarStatus('ocioso')
    if (
      montadoRef.current &&
      fluxo.conversaId &&
      conversaIdRef.current === fluxo.conversaId
    ) {
      void carregarMensagens(fluxo.conversaId)
    }
  }, [carregarMensagens, mudarStatus])

  const reenviar = useCallback(() => {
    if (!textoParaReenviar) return
    const texto = textoParaReenviar
    setTextoParaReenviar(null)
    setMensagens((atuais) =>
      atuais.filter((mensagem) => mensagem.status !== 'erro'),
    )
    setErro(null)
    void enviar(texto)
  }, [enviar, textoParaReenviar])

  const novaConversa = useCallback(() => {
    const fluxo = fluxoRef.current
    conversaIdRef.current = null
    setConversaId(null)
    setMensagens([])
    setErro(null)
    setTextoParaReenviar(null)
    mudarStatus(fluxo ? 'transmitindo' : 'ocioso')
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
