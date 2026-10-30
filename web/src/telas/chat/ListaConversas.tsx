import { useMemo } from 'react'
import { useChat } from '../../chat/contexto'
import { agruparConversas, formatarHora, tituloDaConversa } from '../../dominios/texto'
import estilos from './Chat.module.css'

function dataCurta(iso: string, grupo: string): string {
  if (grupo === 'Hoje' || grupo === 'Ontem') return formatarHora(iso)
  const data = new Date(iso)
  if (Number.isNaN(data.getTime())) return ''
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit',
  }).format(data)
}

export function ListaConversas({ aoSelecionar }: { aoSelecionar?: () => void }) {
  const { conversas, conversaId, carregandoConversas, selecionarConversa } = useChat()

  const grupos = useMemo(() => agruparConversas(conversas), [conversas])

  if (carregandoConversas && conversas.length === 0) {
    return (
      <div aria-busy="true" aria-label="Carregando conversas">
        <div className={estilos.esqueleto} />
        <div className={estilos.esqueleto} />
        <div className={estilos.esqueleto} />
      </div>
    )
  }

  if (conversas.length === 0) {
    return (
      <p className={estilos.vazioLista}>
        Nenhuma conversa ainda. Comece com o que estiver na cabeça.
      </p>
    )
  }

  return (
    <nav aria-label="Conversas">
      {grupos.map(({ grupo, conversas: lista }) => (
        <section key={grupo} className={estilos.grupo}>
          <h2 className={estilos.grupoTitulo}>{grupo}</h2>
          {lista.map((conversa) => {
            const ativa = conversa.id === conversaId
            return (
              <button
                key={conversa.id}
                type="button"
                className={`${estilos.item} ${ativa ? estilos.itemAtivo : ''}`}
                aria-current={ativa ? 'true' : undefined}
                onClick={() => {
                  selecionarConversa(conversa.id)
                  aoSelecionar?.()
                }}
              >
                <span className={estilos.itemTitulo}>{tituloDaConversa(conversa)}</span>
                <span className={estilos.itemData}>
                  {dataCurta(conversa.atualizada_em, grupo)}
                </span>
              </button>
            )
          })}
        </section>
      ))}
    </nav>
  )
}
