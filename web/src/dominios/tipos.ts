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
  fontes?: Fonte[]
}

export interface Fonte {
  titulo?: string
  url: string
  trecho?: string
  data?: string
}

export interface UsoLLM {
  prompt_tokens: number | null
  completion_tokens: number | null
  total_tokens: number | null
}

export type CategoriaMemoria =
  'familia' | 'trabalho' | 'gostos' | 'rotina' | 'saude' | 'outro'

export interface Memoria {
  id: string
  pessoa_id: string
  texto: string
  categoria: CategoriaMemoria
  criada_em: string
}

export type TipoAjuste =
  | 'apelido'
  | 'piada_interna'
  | 'formato'
  | 'assunto'
  | 'nivel_sarcasmo'
  | 'formalidade'
  | 'nivel_tecnico'
  | 'toque_yandere'

export interface Ajuste {
  id: string
  pessoa_id: string
  tipo: TipoAjuste
  texto: string | null
  valor: string | null
  origem: 'conversa' | 'manual'
  criada_em: string
}

export interface AtualizacaoMemoria {
  texto?: string
  categoria?: CategoriaMemoria
}

export interface AtualizacaoAjuste {
  texto?: string | null
  valor?: string | null
}

export interface DadosExportados {
  gerado_em: string
  pessoa: Pessoa
  memorias: Memoria[]
  ajustes: Ajuste[]
  conversas: Array<Conversa & { mensagens: Mensagem[] }>
}

export interface EntradaPessoa {
  nome: string
  faixa_etaria: FaixaEtaria
  perfil: Perfil
}

export interface EntradaChat {
  mensagem: string
  conversaId?: string
  fonte?: 'jw'
}

export type EventoChat =
  | { tipo: 'start'; conversaId: string; mensagemId: string }
  | { tipo: 'token'; texto: string }
  | { tipo: 'sources'; fontes: Fonte[] }
  | {
      tipo: 'done'
      conversaId: string
      mensagemId: string
      modelo: string
      uso: UsoLLM | null
    }
  | { tipo: 'error'; codigo: string; detalhe: string }
