import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Mensagem } from '../../dominios/tipos'
import { MensagemItem } from './MensagemItem'

const CRIADA_EM = new Date(2026, 0, 2, 9, 5).toISOString()

function mensagem(extra: Partial<Mensagem> = {}): Mensagem {
  return {
    id: 'm1',
    papel: 'assistant',
    conteudo: 'Olá, Maria!',
    status: 'completa',
    criada_em: CRIADA_EM,
    ...extra,
  }
}

describe('MensagemItem', () => {
  it('mostra a mensagem da pessoa com hora', () => {
    render(
      <MensagemItem
        mensagem={mensagem({ papel: 'user', conteudo: 'Oi, Sera' })}
        transcrevendo={false}
      />,
    )
    expect(screen.getByText('Oi, Sera')).toBeInTheDocument()
    expect(screen.getByText('09:05')).toBeInTheDocument()
  })

  it('marca a mensagem da pessoa que não foi enviada', () => {
    render(
      <MensagemItem
        mensagem={mensagem({ papel: 'user', status: 'erro' })}
        transcrevendo={false}
      />,
    )
    expect(screen.getByText('não enviada')).toBeInTheDocument()
  })

  it('mostra os pontos enquanto a resposta está vazia', () => {
    render(<MensagemItem mensagem={mensagem({ conteudo: '' })} transcrevendo />)
    expect(screen.getByLabelText('A Sera está escrevendo')).toBeInTheDocument()
  })

  it('mostra o texto e marca a resposta interrompida', () => {
    render(
      <MensagemItem
        mensagem={mensagem({ conteudo: 'pela metade', status: 'interrompida' })}
        transcrevendo={false}
      />,
    )
    expect(screen.getByText(/pela metade/)).toBeInTheDocument()
    expect(screen.getByText('resposta interrompida')).toBeInTheDocument()
    expect(screen.queryByLabelText('A Sera está escrevendo')).not.toBeInTheDocument()
  })
})
