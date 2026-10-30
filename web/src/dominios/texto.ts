import type { Conversa, FaixaEtaria, Perfil } from './tipos'

export const ROTULO_FAIXA: Record<FaixaEtaria, string> = {
  adulto: 'Adulto',
  adolescente: 'Adolescente',
  crianca: 'Criança',
}

export const ROTULO_PERFIL: Record<Perfil, string> = {
  padrao: 'Do meu jeito',
  crianca_adolescente: 'Mais leve',
  idoso_ou_pouco_tecnico: 'Com calma',
}

export const DESCRICAO_PERFIL: Record<Perfil, string> = {
  padrao: 'Conversa normal, com humor quando couber.',
  crianca_adolescente: 'Sem sarcasmo pesado e sem drama.',
  idoso_ou_pouco_tecnico: 'Explicações mais diretas, com paciência.',
}

export const LIMITE_MENSAGEM = 8000

export function tituloDaConversa(conversa: Conversa): string {
  const titulo = conversa.titulo?.trim()
  if (titulo) return titulo
  const data = new Date(conversa.atualizada_em)
  if (Number.isNaN(data.getTime())) return 'Conversa sem título'
  const dia = new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit',
  }).format(data)
  return `Conversa de ${dia} ${formatarHora(conversa.atualizada_em)}`
}

export function primeiroNome(nome: string): string {
  return nome.trim().split(/\s+/)[0] ?? nome
}

export function iniciais(nome: string): string {
  const partes = nome.trim().split(/\s+/).filter(Boolean)
  const primeira = partes[0]?.[0] ?? 'S'
  const ultima = partes.length > 1 ? partes[partes.length - 1]?.[0] : ''
  return `${primeira}${ultima}`.toUpperCase()
}

export function formatarHora(iso: string): string {
  const data = new Date(iso)
  if (Number.isNaN(data.getTime())) return ''
  return new Intl.DateTimeFormat('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(data)
}

function inicioDoDia(data: Date): number {
  return new Date(data.getFullYear(), data.getMonth(), data.getDate()).getTime()
}

export type GrupoConversas = 'Hoje' | 'Ontem' | 'Últimos 7 dias' | 'Mais antigas'

const ORDEM_GRUPOS: GrupoConversas[] = [
  'Hoje',
  'Ontem',
  'Últimos 7 dias',
  'Mais antigas',
]

export interface GrupoDeConversas {
  grupo: GrupoConversas
  conversas: Conversa[]
}

export function agruparConversas(
  conversas: Conversa[],
  agora: Date = new Date(),
): GrupoDeConversas[] {
  const hoje = inicioDoDia(agora)
  const ontem = hoje - 24 * 60 * 60 * 1000
  const seteDias = hoje - 6 * 24 * 60 * 60 * 1000
  const mapa = new Map<GrupoConversas, Conversa[]>()

  for (const conversa of conversas) {
    const data = new Date(conversa.atualizada_em)
    const dia = Number.isNaN(data.getTime()) ? 0 : inicioDoDia(data)
    let grupo: GrupoConversas = 'Mais antigas'
    if (dia === hoje) grupo = 'Hoje'
    else if (dia === ontem) grupo = 'Ontem'
    else if (dia >= seteDias) grupo = 'Últimos 7 dias'
    const lista = mapa.get(grupo) ?? []
    lista.push(conversa)
    mapa.set(grupo, lista)
  }

  return ORDEM_GRUPOS.flatMap((grupo) => {
    const lista = mapa.get(grupo)
    return lista && lista.length > 0 ? [{ grupo, conversas: lista }] : []
  })
}

export function normalizarMensagem(texto: string): string {
  return texto.replace(/\r\n/g, '\n').trim()
}
