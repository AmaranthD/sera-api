import { describe, expect, it } from 'vitest'
import {
  chaveDoDia,
  contagemRegressiva,
  diferencaEmDias,
  faixaDeDias,
  rotuloCurtoDoDia,
  rotuloDoGrupo,
} from './dias'

const agora = new Date(2026, 10, 6, 12, 0).getTime()

function emHoras(horas: number): string {
  return new Date(agora + horas * 60 * 60 * 1000).toISOString()
}

describe('chaveDoDia', () => {
  it('usa ano, mês e dia locais com dois dígitos', () => {
    expect(chaveDoDia(new Date(2026, 0, 2))).toBe('2026-01-02')
  })
})

describe('diferencaEmDias', () => {
  it('conta dias de calendário', () => {
    expect(diferencaEmDias(emHoras(2), agora)).toBe(0)
    expect(diferencaEmDias(emHoras(26), agora)).toBe(1)
    expect(diferencaEmDias(emHoras(-26), agora)).toBe(-1)
  })
})

describe('rotuloDoGrupo', () => {
  it('nomeia os grupos relativos', () => {
    expect(rotuloDoGrupo(emHoras(-26), agora)).toBe('Em andamento')
    expect(rotuloDoGrupo(emHoras(2), agora)).toBe('Hoje')
    expect(rotuloDoGrupo(emHoras(26), agora)).toBe('Amanhã')
    expect(rotuloDoGrupo(emHoras(24 * 3), agora)).toBe('Esta semana')
    expect(rotuloDoGrupo(emHoras(24 * 7), agora)).toBe('Depois')
  })
})

describe('contagemRegressiva', () => {
  it('mostra minutos, horas e dias restantes', () => {
    expect(contagemRegressiva(emHoras(0.5), emHoras(1.5), agora)).toBe('em 30 min')
    expect(contagemRegressiva(emHoras(2), emHoras(3), agora)).toBe('em 2h')
    expect(contagemRegressiva(emHoras(2.5), emHoras(3.5), agora)).toBe('em 2h 30min')
    expect(contagemRegressiva(emHoras(25), emHoras(26), agora)).toBe('em 1 dia')
    expect(contagemRegressiva(emHoras(49), emHoras(50), agora)).toBe('em 2 dias')
  })

  it('trata compromisso em andamento e encerrado', () => {
    expect(contagemRegressiva(emHoras(-1), emHoras(1), agora)).toBe('agora')
    expect(contagemRegressiva(emHoras(-2), emHoras(-1), agora)).toBe('')
  })

  it('devolve string vazia para data inválida', () => {
    expect(contagemRegressiva('não é data', emHoras(1), agora)).toBe('')
  })
})

describe('faixaDeDias', () => {
  it('começa hoje e cobre sete dias', () => {
    const dias = faixaDeDias(agora)
    expect(dias).toHaveLength(7)
    expect(chaveDoDia(dias[0] as Date)).toBe('2026-11-06')
    expect(chaveDoDia(dias[6] as Date)).toBe('2026-11-12')
  })
})

describe('rotuloCurtoDoDia', () => {
  it('devolve um rótulo curto sem ponto', () => {
    const rotulo = rotuloCurtoDoDia(new Date(2026, 10, 6))
    expect(rotulo.length).toBeGreaterThan(0)
    expect(rotulo).not.toContain('.')
  })
})
