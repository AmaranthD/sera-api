import { describe, expect, it } from 'vitest'
import { traduzirErroAuth } from './supabase'

function mensagem(erro: string): string {
  return traduzirErroAuth(erro).message
}

describe('traduzirErroAuth', () => {
  it('explica quando o e-mail não está autorizado no SMTP padrão', () => {
    expect(mensagem('Email address not authorized')).toContain('liberado')
    expect(mensagem('email_address_not_authorized')).toContain('liberado')
  })

  it('pede para esperar em caso de limite de envio', () => {
    expect(mensagem('over_email_send_rate_limit')).toContain('Muitos pedidos')
    expect(
      mensagem('For security purposes, you can only request this after 60 seconds'),
    ).toContain('Muitos pedidos')
  })

  it('diferencia e-mail inválido de e-mail não autorizado', () => {
    expect(mensagem('Invalid email address')).toBe('Esse e-mail não parece válido.')
    expect(mensagem('Email address not authorized')).not.toBe(
      'Esse e-mail não parece válido.',
    )
  })

  it('traduz link expirado, cadastro fechado e provedor desligado', () => {
    expect(mensagem('Email link is invalid or has expired')).toContain('expirou')
    expect(mensagem('Signups not allowed for this instance')).toContain('liberada')
    expect(mensagem('Email logins are disabled')).toContain('desativado')
  })

  it('usa a mensagem genérica para o desconhecido', () => {
    expect(mensagem('boom')).toBe(
      'Não foi possível entrar agora. Tente de novo em instantes.',
    )
  })
})
