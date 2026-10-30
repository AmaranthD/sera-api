export type FaixaEtaria = 'adulto' | 'adolescente' | 'crianca'

export type Perfil = 'padrao' | 'crianca_adolescente' | 'idoso_ou_pouco_tecnico'

export type Papel = 'user' | 'assistant'

export type StatusMensagem = 'completa' | 'interrompida' | 'erro'

export interface Pessoa {
  id: string
  nome: string
  faixa_etaria: FaixaEtaria
  perfil: Perfil
  acesso_vault: boolean
  criada_em: string
}

export interface Conversa {
  id: string
  pessoa_id: string
  titulo: string | null
  criada_em: string
  atualizada_em: string
}

export interface Mensagem {
  id: string
  conversa_id?: string
  papel: Papel
  conteudo: string
  status: StatusMensagem
  criada_em: string
}

export interface UsoLLM {
  prompt_tokens: number | null
  completion_tokens: number | null
  total_tokens: number | null
}

export interface EntradaPessoa {
  nome: string
  faixa_etaria: FaixaEtaria
  perfil: Perfil
}

export interface EntradaChat {
  mensagem: string
  conversaId?: string
}

export type EventoChat =
  | { tipo: 'start'; conversaId: string; mensagemId: string }
  | { tipo: 'token'; texto: string }
  | {
      tipo: 'done'
      conversaId: string
      mensagemId: string
      modelo: string
      uso: UsoLLM | null
    }
  | { tipo: 'error'; codigo: string; detalhe: string }
