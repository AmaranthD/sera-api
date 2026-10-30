import { describe, expect, it } from 'vitest'
import type { Conversa } from './tipos'
import {
  agruparConversas,
  formatarHora,
  iniciais,
  normalizarMensagem,
  primeiroNome,
  tituloDaConversa,
} from './texto'

function conversa(
  id: string,
  atualizadaEm: Date,
  titulo: string | null = null,
): Conversa {
  const iso = Number.isNaN(atualizadaEm.getTime())
    ? 'data-invalida'
    : atualizadaEm.toISOString()
  return {
    id,
    pessoa_id: 'p1',
    titulo,
    criada_em: iso,
    atualizada_em: iso,
  }
}

describe('tituloDaConversa', () => {
  it('usa o título salvo', () => {
    expect(tituloDaConversa(conversa('c1', new Date(), 'Almoço'))).toBe('Almoço')
  })

  it('usa data e hora quando o título é vazio', () => {
    const data = new Date(2026, 0, 2, 9, 5)
    expect(tituloDaConversa(conversa('c1', data, '   '))).toBe(
      'Conversa de 02/01 09:05',
    )
  })
})

describe('nomes', () => {
  it('extrai o primeiro nome', () => {
    expect(primeiroNome('  Maria da Silva ')).toBe('Maria')
  })

  it('monta iniciais com primeira e última palavra', () => {
    expect(iniciais('Maria da Silva')).toBe('MS')
    expect(iniciais('ana')).toBe('A')
    expect(iniciais('   ')).toBe('S')
  })
})

describe('normalizarMensagem', () => {
  it('converte CRLF e remove espaços das pontas', () => {
    expect(normalizarMensagem('  oi\r\nmundo  ')).toBe('oi\nmundo')
  })
})

describe('formatarHora', () => {
  it('formata em 24 horas', () => {
    const data = new Date(2026, 0, 2, 9, 5)
    expect(formatarHora(data.toISOString())).toBe('09:05')
  })

  it('devolve string vazia para data inválida', () => {
    expect(formatarHora('não é data')).toBe('')
  })
})

describe('agruparConversas', () => {
  const agora = new Date(2026, 5, 15, 12, 0)

  it('agrupa por hoje, ontem, últimos 7 dias e mais antigas', () => {
    const grupos = agruparConversas(
      [
        conversa('hoje', new Date(2026, 5, 15, 9, 0)),
        conversa('ontem', new Date(2026, 5, 14, 9, 0)),
        conversa('semana', new Date(2026, 5, 11, 9, 0)),
        conversa('antiga', new Date(2026, 4, 1, 9, 0)),
      ],
      agora,
    )

    expect(grupos.map((grupo) => grupo.grupo)).toEqual([
      'Hoje',
      'Ontem',
      'Últimos 7 dias',
      'Mais antigas',
    ])
    expect(grupos.flatMap((grupo) => grupo.conversas.map((item) => item.id))).toEqual([
      'hoje',
      'ontem',
      'semana',
      'antiga',
    ])
  })

  it('omite grupos vazios e mantém a ordem recebida dentro do grupo', () => {
    const grupos = agruparConversas(
      [
        conversa('a', new Date(2026, 5, 15, 10, 0)),
        conversa('b', new Date(2026, 5, 15, 11, 0)),
      ],
      agora,
    )

    expect(grupos).toHaveLength(1)
    expect(grupos[0]?.conversas.map((item) => item.id)).toEqual(['a', 'b'])
  })

  it('trata data inválida como mais antiga', () => {
    const grupos = agruparConversas([conversa('x', new Date(NaN))], agora)
    expect(grupos[0]?.grupo).toBe('Mais antigas')
  })
})
