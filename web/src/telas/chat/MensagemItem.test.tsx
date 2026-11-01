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

  it('interpreta markdown da Sera com links seguros', () => {
    render(
      <MensagemItem
        mensagem={mensagem({
          conteudo: 'Olá, **Maria**!\n\n- um\n- dois\n\n[Site](https://example.com)',
        })}
        transcrevendo={false}
      />,
    )

    expect(screen.getByText('Maria').tagName).toBe('STRONG')
    expect(screen.getByRole('list')).toBeInTheDocument()

    const link = screen.getByRole('link', { name: 'Site' })
    expect(link).toHaveAttribute('href', 'https://example.com')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer nofollow')
  })

  it('não renderiza HTML bruto vindo da resposta', () => {
    render(
      <MensagemItem
        mensagem={mensagem({
          conteudo: '<img src="x" onerror="alert(1)"> **seguro**',
        })}
        transcrevendo={false}
      />,
    )

    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.getByText('seguro').tagName).toBe('STRONG')
  })

  it('não interpreta markdown na mensagem da pessoa', () => {
    render(
      <MensagemItem
        mensagem={mensagem({ papel: 'user', conteudo: '**oi**' })}
        transcrevendo={false}
      />,
    )

    expect(screen.getByText('**oi**')).toBeInTheDocument()
  })
})

describe('MensagemItem com fontes', () => {
  const URL_BIBLIA = 'https://www.jw.org/finder?wtlocale=E&bible=19123001'
  const FONTES = [
    {
      titulo: 'JW · Bíblia',
      url: URL_BIBLIA,
    },
    {
      titulo: 'JW · A Sentinela',
      url: 'https://cfp2.jw-cdn.org/a/exemplo.rtf',
    },
  ]

  it('mostra a lista de fontes depois do texto', () => {
    render(
      <MensagemItem
        mensagem={mensagem({ conteudo: 'O Senhor é meu pastor.', fontes: FONTES })}
        transcrevendo={false}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Fontes' })).toBeInTheDocument()
    const link = screen.getByRole('link', { name: 'JW · Bíblia' })
    expect(link).toHaveAttribute('href', URL_BIBLIA)
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer nofollow')
    expect(screen.getByRole('link', { name: 'JW · A Sentinela' })).toBeInTheDocument()
  })

  it('não mostra fontes enquanto a resposta está sendo escrita', () => {
    render(
      <MensagemItem
        mensagem={mensagem({ conteudo: 'O Senhor é', fontes: FONTES })}
        transcrevendo
      />,
    )
    expect(screen.queryByRole('heading', { name: 'Fontes' })).not.toBeInTheDocument()
  })

  it('não renderiza URL que não seja http(s)', () => {
    render(
      <MensagemItem
        mensagem={mensagem({
          fontes: [{ titulo: 'Perigo', url: 'javascript:alert(1)' }],
        })}
        transcrevendo={false}
      />,
    )
    expect(screen.queryByRole('heading', { name: 'Fontes' })).not.toBeInTheDocument()
  })
})
