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
  if (
    texto.includes('not authorized') ||
    texto.includes('email_address_not_authorized')
  ) {
    return new ErroAutenticacao(
      'Este e-mail ainda não está liberado para receber o acesso. Peça para quem cuida da Sera liberar o endereço.',
    )
  }
  if (
    texto.includes('rate limit') ||
    texto.includes('rate_limit') ||
    texto.includes('too many') ||
    texto.includes('security purposes')
  ) {
    return new ErroAutenticacao(
      'Muitos pedidos de acesso. Espere alguns minutos antes de tentar de novo.',
    )
  }
  if (texto.includes('invalid email') || texto.includes('email format')) {
    return new ErroAutenticacao('Esse e-mail não parece válido.')
  }
  if (texto.includes('expired') || texto.includes('invalid token')) {
    return new ErroAutenticacao('Esse código ou link expirou. Peça um novo acesso.')
  }
  if (texto.includes('signups not allowed') || texto.includes('not allowed')) {
    return new ErroAutenticacao(
      'Essa conta ainda não foi liberada. Fale com quem cuida da Sera.',
    )
  }
  if (texto.includes('email provider') || texto.includes('email logins are disabled')) {
    return new ErroAutenticacao(
      'O acesso por e-mail está desativado no momento. Fale com quem cuida da Sera.',
    )
  }
  return new ErroAutenticacao(
    'Não foi possível entrar agora. Tente de novo em instantes.',
  )
}
