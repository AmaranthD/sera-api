import { createContext, useContext } from 'react'
import type { Conversa, Mensagem } from '../dominios/tipos'

export type StatusChat = 'ocioso' | 'enviando' | 'transmitindo' | 'erro'

export interface ValorChat {
  conversas: Conversa[]
  conversaId: string | null
  conversaAtual: Conversa | null
  mensagens: Mensagem[]
  status: StatusChat
  erro: string | null
  carregandoConversas: boolean
  carregandoMensagens: boolean
  podeReenviar: boolean
  enviar: (texto: string) => Promise<void>
  parar: () => void
  reenviar: () => void
  novaConversa: () => void
  selecionarConversa: (id: string) => void
  recarregarConversas: () => Promise<void>
  recarregarConversa: () => Promise<void>
  limparErro: () => void
}

export const ChatContext = createContext<ValorChat | null>(null)

export function useChat(): ValorChat {
  const valor = useContext(ChatContext)
  if (!valor) {
    throw new Error('useChat precisa estar dentro de ChatProvider')
  }
  return valor
}
