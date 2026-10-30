export interface Ambiente {
  supabaseUrl: string
  supabaseAnonKey: string
  apiUrl: string
}

export class ErroConfiguracao extends Error {
  constructor(readonly campos: string[]) {
    super(`Configuração ausente ou inválida: ${campos.join(', ')}`)
    this.name = 'ErroConfiguracao'
  }
}

function urlValida(valor: string, nome: string, problemas: string[]): string {
  const limpo = valor.trim().replace(/\/+$/, '')
  if (!limpo) {
    problemas.push(nome)
    return ''
  }
  try {
    const url = new URL(limpo)
    const local = url.hostname === 'localhost' || url.hostname === '127.0.0.1'
    if (url.protocol !== 'https:' && !(local && url.protocol === 'http:')) {
      problemas.push(`${nome} (use https)`)
    }
  } catch {
    problemas.push(`${nome} (URL inválida)`)
  }
  return limpo
}

/** Lê e valida as variáveis públicas do build. Não guarda segredo nenhum. */
export function lerAmbiente(
  fonte: Record<string, string | boolean | undefined> = import.meta.env,
): Ambiente {
  const problemas: string[] = []
  const supabaseUrl = urlValida(
    String(fonte.VITE_SUPABASE_URL ?? ''),
    'VITE_SUPABASE_URL',
    problemas,
  )
  const apiUrl = urlValida(String(fonte.VITE_API_URL ?? ''), 'VITE_API_URL', problemas)
  const chave = String(fonte.VITE_SUPABASE_ANON_KEY ?? '').trim()
  if (!chave) {
    problemas.push('VITE_SUPABASE_ANON_KEY')
  }
  if (problemas.length > 0) {
    throw new ErroConfiguracao(problemas)
  }
  return { supabaseUrl, supabaseAnonKey: chave, apiUrl }
}
