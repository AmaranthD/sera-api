import type { Mensagem } from '../../dominios/tipos'
import { formatarHora } from '../../dominios/texto'
import estilos from './Chat.module.css'

interface Props {
  mensagem: Mensagem
  transcrevendo: boolean
}

export function MensagemItem({ mensagem, transcrevendo }: Props) {
  const data = new Date(mensagem.criada_em)
  const dataCompleta = Number.isNaN(data.getTime())
    ? ''
    : data.toLocaleString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })

  if (mensagem.papel === 'user') {
    return (
      <div className={estilos.balaoUsuario}>
        <p className={estilos.textoMensagem}>{mensagem.conteudo}</p>
        <div className={`${estilos.meta} ${estilos.metaUsuario}`}>
          <time dateTime={mensagem.criada_em} title={dataCompleta}>
            {formatarHora(mensagem.criada_em)}
          </time>
          {mensagem.status === 'erro' ? (
            <span className={estilos.avisoMensagem}>não enviada</span>
          ) : null}
        </div>
      </div>
    )
  }

  const vazia = mensagem.conteudo.length === 0
  return (
    <article className={estilos.assistente} aria-label="Resposta da Sera">
      <span className={estilos.avatarSera} aria-hidden="true">
        S
      </span>
      <div className={estilos.assistenteCorpo}>
        <div className={estilos.balaoAssistente}>
          {vazia && transcrevendo ? (
            <span className={estilos.pontos} aria-label="A Sera está escrevendo">
              <span className={estilos.ponto} />
              <span className={estilos.ponto} />
              <span className={estilos.ponto} />
            </span>
          ) : (
            <p className={estilos.textoMensagem}>
              {mensagem.conteudo}
              {transcrevendo && !vazia ? (
                <span className={estilos.cursor} aria-hidden="true" />
              ) : null}
            </p>
          )}
        </div>
        <div className={estilos.meta}>
          <time dateTime={mensagem.criada_em} title={dataCompleta}>
            {formatarHora(mensagem.criada_em)}
          </time>
          {mensagem.status === 'interrompida' ? (
            <span className={estilos.avisoMensagem}>resposta interrompida</span>
          ) : null}
          {mensagem.status === 'erro' ? (
            <span className={estilos.avisoMensagem}>não foi possível concluir</span>
          ) : null}
        </div>
      </div>
    </article>
  )
}
