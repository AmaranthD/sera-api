import type { Fonte } from '../../dominios/tipos'
import estilos from './Chat.module.css'

export function ListaFontes({ fontes }: { fontes?: Fonte[] }) {
  const validas = (fontes ?? []).filter((fonte) => /^https?:\/\//i.test(fonte.url))
  if (validas.length === 0) return null

  return (
    <section className={estilos.fontes} aria-label="Fontes">
      <h3 className={estilos.fontesTitulo}>Fontes</h3>
      <ol className={estilos.fontesLista}>
        {validas.map((fonte) => (
          <li key={fonte.url}>
            <a href={fonte.url} target="_blank" rel="noopener noreferrer nofollow">
              {fonte.titulo || fonte.url}
            </a>
          </li>
        ))}
      </ol>
    </section>
  )
}
