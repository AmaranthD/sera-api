import { createClient, type SupabaseClient } from '@supabase/supabase-js'
import type { Ambiente } from '../env'

export function criarSupabase(ambiente: Ambiente): SupabaseClient {
  return createClient(ambiente.supabaseUrl, ambiente.supabaseAnonKey, {
    auth: {
      flowType: 'pkce',
      detectSessionInUrl: true,
      persistSession: true,
      autoRefreshToken: true,
    },
  })
}

export class ErroAutenticacao extends Error {
  constructor(mensagem: string) {
    super(mensagem)
    this.name = 'ErroAutenticacao'
  }
}

export function traduzirErroAuth(mensagem: string): ErroAutenticacao {
  const texto = mensagem.toLowerCase()
  if (texto.includes('rate limit') || texto.includes('too many')) {
    return new ErroAutenticacao(
      'Muitos pedidos de acesso. Espere alguns minutos antes de tentar de novo.',
    )
  }
  if (texto.includes('invalid email') || texto.includes('email address')) {
    return new ErroAutenticacao('Esse e-mail não parece válido.')
  }
  if (
    texto.includes('expired') ||
    texto.includes('invalid token') ||
    texto.includes('otp')
  ) {
    return new ErroAutenticacao('Esse código ou link expirou. Peça um novo acesso.')
  }
  if (texto.includes('signups not allowed') || texto.includes('not allowed')) {
    return new ErroAutenticacao(
      'Essa conta ainda não foi liberada. Fale com quem cuida da Sera.',
    )
  }
  return new ErroAutenticacao(
    'Não foi possível entrar agora. Tente de novo em instantes.',
  )
}
