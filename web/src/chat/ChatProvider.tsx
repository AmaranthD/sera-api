import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ehSessaoExpirada, ErroApi } from '../api/erros'
import type { EventoChat } from '../dominios/tipos'
import type { Conversa, Mensagem } from '../dominios/tipos'
import { normalizarMensagem } from '../dominios/texto'
import { useSessao } from '../auth/contexto'
import { usePessoa } from '../pessoa/contexto'
import { ChatContext, type StatusChat } from './contexto'

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

function semAcentoDeErro(erro: unknown): string {
  if (erro instanceof ErroApi) return erro.message
  if (erro instanceof Error) return erro.message
  return 'Não foi possível completar o pedido.'
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
  const emStreamRef = useRef(false)
  const controladorRef = useRef<AbortController | null>(null)
  const montadoRef = useRef(true)

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
        setErro(semAcentoDeErro(falha))
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
      } catch (falha) {
        if (ehSessaoExpirada(falha)) {
          await sair()
          return
        }
        if (conversaIdRef.current !== id) return
        setMensagens([])
        setErro(semAcentoDeErro(falha))
      } finally {
        if (conversaIdRef.current === id) {
          setCarregandoMensagens(false)
        }
      }
    },
    [api, sair],
  )

  // A URL é a fonte da verdade da conversa aberta; o provider sobrevive à
  // troca de rota para não matar o stream.
  useEffect(() => {
    const id = idDaRota(localizacao.pathname)
    if (id === conversaIdRef.current) return

    if (emStreamRef.current) {
      controladorRef.current?.abort()
      emStreamRef.current = false
    }
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
      controladorRef.current?.abort()
    }
  }, [])

  const enviar = useCallback(
    async (bruto: string) => {
      if (emStreamRef.current) return
      const texto = normalizarMensagem(bruto)
      if (!texto) return

      const idConversa = conversaIdRef.current
      const agora = new Date().toISOString()
      const idUsuario = idLocal()
      const idAssistente = idLocal()
      let idUsuarioAtual = idUsuario

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
          status: 'completa',
          criada_em: agora,
        },
      ])
      setErro(null)
      setTextoParaReenviar(null)
      mudarStatus('enviando')
      emStreamRef.current = true

      const controlador = new AbortController()
      controladorRef.current = controlador

      const marcarAssistente = (
        atualizacao: Partial<Mensagem>,
        idAtual = idAssistente,
      ) => {
        setMensagens((atuais) =>
          atuais.map((mensagem) =>
            mensagem.id === idAtual ? { ...mensagem, ...atualizacao } : mensagem,
          ),
        )
      }

      const aoEvento = (evento: EventoChat) => {
        if (evento.tipo === 'start') {
          conversaIdRef.current = evento.conversaId
          setConversaId(evento.conversaId)
          idUsuarioAtual = evento.mensagemId
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
            // A conversa já existe no servidor; atualiza a lista mesmo se a
            // pessoa interromper antes do `done`.
            void carregarConversas()
          }
          return
        }

        if (evento.tipo === 'token') {
          if (statusRef.current === 'enviando') {
            mudarStatus('transmitindo')
          }
          setMensagens((atuais) =>
            atuais.map((mensagem) =>
              mensagem.id === idAssistente
                ? {
                    ...mensagem,
                    conteudo: mensagem.conteudo + evento.texto,
                  }
                : mensagem,
            ),
          )
          return
        }

        if (evento.tipo === 'done') {
          marcarAssistente({ id: evento.mensagemId, status: 'completa' })
          setMensagens((atuais) =>
            atuais.map((mensagem) =>
              mensagem.id === idUsuarioAtual
                ? { ...mensagem, conversa_id: evento.conversaId }
                : mensagem,
            ),
          )
          setTextoParaReenviar(null)
          mudarStatus('ocioso')
          void carregarConversas()
          return
        }

        if (evento.tipo === 'error') {
          marcarAssistente({ status: 'erro' })
          setErro(evento.detalhe)
          setTextoParaReenviar(texto)
          mudarStatus('erro')
        }
      }

      try {
        await api.transmitirChat(
          { mensagem: texto, conversaId: idConversa ?? undefined },
          aoEvento,
          controlador.signal,
        )
        if (statusRef.current !== 'erro') mudarStatus('ocioso')
      } catch (falha) {
        if (falha instanceof DOMException && falha.name === 'AbortError') {
          if (!montadoRef.current) return
          setMensagens((atuais) =>
            atuais.flatMap((mensagem) => {
              if (mensagem.id !== idAssistente) return [mensagem]
              return mensagem.conteudo
                ? [{ ...mensagem, status: 'interrompida' as const }]
                : []
            }),
          )
          mudarStatus('ocioso')
          setTextoParaReenviar(null)
          return
        }
        if (ehSessaoExpirada(falha)) {
          await sair()
          return
        }
        if (!montadoRef.current) return
        marcarAssistente({ status: 'erro' })
        setMensagens((atuais) =>
          atuais.map((mensagem) =>
            mensagem.id === idUsuarioAtual
              ? { ...mensagem, status: 'erro' as const }
              : mensagem,
          ),
        )
        setErro(semAcentoDeErro(falha))
        setTextoParaReenviar(texto)
        mudarStatus('erro')
      } finally {
        emStreamRef.current = false
        if (controladorRef.current === controlador) {
          controladorRef.current = null
        }
      }
    },
    [api, carregarConversas, mudarStatus, navegar, sair],
  )

  const parar = useCallback(() => {
    controladorRef.current?.abort()
  }, [])

  const reenviar = useCallback(() => {
    if (!textoParaReenviar) return
    const texto = textoParaReenviar
    setTextoParaReenviar(null)
    setMensagens((atuais) => atuais.filter((mensagem) => mensagem.status !== 'erro'))
    setErro(null)
    void enviar(texto)
  }, [enviar, textoParaReenviar])

  const novaConversa = useCallback(() => {
    controladorRef.current?.abort()
    conversaIdRef.current = null
    setConversaId(null)
    setMensagens([])
    setErro(null)
    setTextoParaReenviar(null)
    mudarStatus('ocioso')
    navegar('/')
  }, [mudarStatus, navegar])

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
