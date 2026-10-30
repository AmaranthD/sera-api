import estilos from './Carregando.module.css'

export function CarregandoTela({ texto = 'Abrindo a Sera…' }: { texto?: string }) {
  return (
    <div className={estilos.tela} role="status" aria-live="polite">
      <div className={estilos.conteudo}>
        <span className={estilos.selo} aria-hidden="true">
          S
        </span>
        <span>{texto}</span>
      </div>
    </div>
  )
}

export function CarregandoLinha({ texto }: { texto: string }) {
  return (
    <span className={estilos.inline} role="status">
      <span className={estilos.pontos} aria-hidden="true">
        <span className={estilos.ponto} />
        <span className={estilos.ponto} />
        <span className={estilos.ponto} />
      </span>
      {texto}
    </span>
  )
}
