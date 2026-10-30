import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useChat } from '../../chat/contexto'
import { usePessoa } from '../../pessoa/contexto'
import { primeiroNome, tituloDaConversa } from '../../dominios/texto'
import { Marca } from '../../componentes/Marca'
import { Icone } from '../../componentes/Icone'
import { MensagemItem } from './MensagemItem'
import estilos from './Chat.module.css'

const SUGESTOES = [
  'Como foi seu dia?',
  'Me ajuda a organizar uma ideia',
  'Quero só conversar',
]

export function PainelConversa({ aoSugerir }: { aoSugerir: (texto: string) => void }) {
  const { pessoa } = usePessoa()
  const { mensagens, status, carregandoMensagens, conversaId, conversaAtual } =
    useChat()

  const rolagemRef = useRef<HTMLDivElement>(null)
  const fimRef = useRef<HTMLDivElement>(null)
  const quantidadeAnterior = useRef(0)
  const statusAnterior = useRef(status)
  const [pertoDoFim, setPertoDoFim] = useState(true)
  const [anuncio, setAnuncio] = useState('')

  const transcrevendo =
    (status === 'enviando' || status === 'transmitindo') &&
    mensagens[mensagens.length - 1]?.papel === 'assistant'

  const rolarParaFim = (comportamento: ScrollBehavior = 'smooth') => {
    fimRef.current?.scrollIntoView({ behavior: comportamento, block: 'end' })
  }

  useLayoutEffect(() => {
    const ultima = mensagens[mensagens.length - 1]
    const novaDoUsuario =
      ultima?.papel === 'user' && mensagens.length > quantidadeAnterior.current
    const primeiraCarga = quantidadeAnterior.current === 0 && mensagens.length > 0

    if (pertoDoFim || novaDoUsuario || primeiraCarga) {
      rolarParaFim(primeiraCarga ? 'auto' : 'smooth')
    }
    quantidadeAnterior.current = mensagens.length
  }, [mensagens, pertoDoFim])

  useEffect(() => {
    const antes = statusAnterior.current
    const terminou =
      (antes === 'enviando' || antes === 'transmitindo') && status === 'ocioso'
    if (terminou) {
      const ultima = [...mensagens]
        .reverse()
        .find(
          (mensagem) => mensagem.papel === 'assistant' && mensagem.conteudo.length > 0,
        )
      if (ultima) {
        setAnuncio(`Resposta da Sera: ${ultima.conteudo.slice(0, 500)}`)
      }
    }
    statusAnterior.current = status
  }, [status, mensagens])

  if (carregandoMensagens) {
    return (
      <div className={estilos.carregandoMensagens} aria-busy="true">
        <div className={estilos.esqueletoMensagem} />
        <div
          className={`${estilos.esqueletoMensagem} ${estilos.esqueletoMensagemCurta}`}
        />
        <div className={estilos.esqueletoMensagem} />
      </div>
    )
  }

  if (!conversaId && mensagens.length === 0) {
    return (
      <div className={estilos.boasVindas}>
        <div className={estilos.boasVindasCartao}>
          <div className={estilos.boasVindasMarca}>
            <Marca pequena legenda="conversa" />
          </div>
          <h2 className={estilos.boasVindasTitulo}>
            Oi, {pessoa ? primeiroNome(pessoa.nome) : 'tudo bem'}.
          </h2>
          <p className={estilos.boasVindasTexto}>
            Pode falar do seu dia, pedir ajuda para pensar em algo ou só conversar. Não
            tem jeito certo de começar.
          </p>
          <div className={estilos.sugestoes} aria-label="Sugestões">
            {SUGESTOES.map((sugestao) => (
              <button
                key={sugestao}
                type="button"
                className={estilos.sugestao}
                onClick={() => aoSugerir(sugestao)}
              >
                {sugestao}
              </button>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div
      className={estilos.rolagem}
      ref={rolagemRef}
      onScroll={(evento) => {
        const alvo = evento.currentTarget
        const distancia = alvo.scrollHeight - alvo.scrollTop - alvo.clientHeight
        setPertoDoFim(distancia < 120)
      }}
    >
      <div
        className={`${estilos.mensagens} ${
          mensagens.length === 0 ? estilos.mensagensVazias : ''
        }`}
        role="log"
        aria-label="Mensagens da conversa"
      >
        {conversaAtual ? (
          <span className="srOnly">Conversa: {tituloDaConversa(conversaAtual)}</span>
        ) : null}
        {mensagens.map((mensagem) => (
          <MensagemItem
            key={mensagem.id}
            mensagem={mensagem}
            transcrevendo={
              transcrevendo && mensagem === mensagens[mensagens.length - 1]
            }
          />
        ))}
        {!conversaId && mensagens.length === 0 ? (
          <p className={estilos.vazioLista}>Comece escrevendo abaixo.</p>
        ) : null}
        {conversaId && mensagens.length === 0 ? (
          <p className={estilos.vazioLista}>
            Essa conversa ainda não tem mensagens. Escreva abaixo para começar.
          </p>
        ) : null}
        <div ref={fimRef} />
      </div>

      <div className="srOnly" aria-live="polite" aria-atomic="true">
        {anuncio}
      </div>

      {!pertoDoFim && mensagens.length > 0 ? (
        <button
          type="button"
          className={estilos.irParaFim}
          onClick={() => {
            setPertoDoFim(true)
            rolarParaFim()
          }}
        >
          <Icone nome="voltar" tamanho={15} />
          Ir para o fim
        </button>
      ) : null}
    </div>
  )
}
