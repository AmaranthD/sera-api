import { describe, expect, it } from 'vitest'
import type { Pessoa } from '../dominios/tipos'
import { selecionarPessoa } from './selecionar'

const ANA: Pessoa = {
  id: 'ana',
  nome: 'Ana',
  faixa_etaria: 'adulto',
  perfil: 'padrao',
  acesso_vault: true,
  criada_em: '2026-01-01T00:00:00Z',
}

const JOANA: Pessoa = {
  ...ANA,
  id: 'joana',
  nome: 'Joana',
}

describe('selecionarPessoa', () => {
  it('escolhe pelo id da sessão, não pela posição', () => {
    expect(selecionarPessoa([ANA, JOANA], 'joana')).toEqual(JOANA)
    expect(selecionarPessoa([JOANA, ANA], 'ana')).toEqual(ANA)
  })

  it('não usa outra pessoa quando há várias e nenhuma bate', () => {
    expect(selecionarPessoa([ANA, JOANA], 'maria')).toBeNull()
  })

  it('aceita a única pessoa em ambiente sem auth', () => {
    expect(selecionarPessoa([ANA], 'id-que-nao-bate')).toEqual(ANA)
  })

  it('sem sessão não escolhe ninguém', () => {
    expect(selecionarPessoa([ANA], null)).toBeNull()
  })
})
