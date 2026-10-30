import estilos from './Marca.module.css'

interface Props {
  clara?: boolean
  pequena?: boolean
  somenteMonograma?: boolean
  legenda?: string
}

export function Marca({
  clara = false,
  pequena = false,
  somenteMonograma = false,
  legenda,
}: Props) {
  const classes = [
    estilos.marca,
    clara ? estilos.clara : '',
    pequena ? estilos.pequena : '',
    somenteMonograma ? estilos.somenteMonograma : '',
  ]
    .filter(Boolean)
    .join(' ')
  return (
    <span className={classes} aria-label="Sera">
      <span className={estilos.monograma} aria-hidden="true">
        S
      </span>
      {somenteMonograma ? null : (
        <span className={estilos.texto}>
          <span className={estilos.nome}>Sera</span>
          {legenda ? <span className={estilos.legenda}>{legenda}</span> : null}
        </span>
      )}
    </span>
  )
}
