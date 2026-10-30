import { describe, expect, it } from 'vitest'
import { ErroConfiguracao, lerAmbiente } from './env'

const VALIDO = {
  VITE_SUPABASE_URL: 'https://abc.supabase.co',
  VITE_SUPABASE_ANON_KEY: 'chave-publica',
  VITE_API_URL: 'https://api.exemplo.com',
}

describe('lerAmbiente', () => {
  it('lê e normaliza as variáveis', () => {
    expect(
      lerAmbiente({
        ...VALIDO,
        VITE_SUPABASE_URL: 'https://abc.supabase.co/',
        VITE_API_URL: ' https://api.exemplo.com// ',
      }),
    ).toEqual({
      supabaseUrl: 'https://abc.supabase.co',
      supabaseAnonKey: 'chave-publica',
      apiUrl: 'https://api.exemplo.com',
    })
  })

  it('aceita http apenas em localhost', () => {
    expect(
      lerAmbiente({ ...VALIDO, VITE_API_URL: 'http://localhost:8000' }).apiUrl,
    ).toBe('http://localhost:8000')

    expect(() =>
      lerAmbiente({ ...VALIDO, VITE_API_URL: 'http://api.exemplo.com' }),
    ).toThrow(ErroConfiguracao)
  })

  it('lista todos os campos ausentes de uma vez', () => {
    try {
      lerAmbiente({})
      expect.unreachable('deveria falhar')
    } catch (erro) {
      expect(erro).toBeInstanceOf(ErroConfiguracao)
      expect((erro as ErroConfiguracao).campos).toEqual([
        'VITE_SUPABASE_URL',
        'VITE_API_URL',
        'VITE_SUPABASE_ANON_KEY',
      ])
    }
  })

  it('recusa URL inválida', () => {
    expect(() => lerAmbiente({ ...VALIDO, VITE_API_URL: 'api.exemplo.com' })).toThrow(
      ErroConfiguracao,
    )
  })

  it('recusa chave anônima vazia', () => {
    expect(() => lerAmbiente({ ...VALIDO, VITE_SUPABASE_ANON_KEY: '   ' })).toThrow(
      ErroConfiguracao,
    )
  })
})
