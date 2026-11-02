import { describe, expect, it } from 'vitest'
import { textoParaFala } from './falar'
import { mensagemDeErroVoz, reconhecimentoSuportado } from './ouvir'

describe('textoParaFala', () => {
  it('remove marcação, código e URLs', () => {
    const texto = [
      '## Título',
      '',
      '**Oi**, veja [o link](https://exemplo.com).',
      '',
      '```js',
      'console.log(1)',
      '```',
    ].join('\n')

    expect(textoParaFala(texto)).toBe('Título Oi, veja o link.')
  })

  it('devolve vazio quando não sobra texto', () => {
    expect(textoParaFala('```\nhttp://x\n```')).toBe('')
  })
})

describe('reconhecimento de voz', () => {
  it('não está disponível no jsdom', () => {
    expect(reconhecimentoSuportado()).toBe(false)
  })

  it('traduz erros comuns', () => {
    expect(mensagemDeErroVoz('not-allowed')).toContain('Permissão')
    expect(mensagemDeErroVoz('network')).toContain('Sem conexão')
  })
})
