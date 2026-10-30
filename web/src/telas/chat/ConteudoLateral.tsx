import { Link } from 'react-router-dom'
import { useChat } from '../../chat/contexto'
import { usePessoa } from '../../pessoa/contexto'
import { iniciais } from '../../dominios/texto'
import { Botao } from '../../componentes/Botao'
import { BotaoInstalar } from '../../componentes/BotaoInstalar'
import { Icone } from '../../componentes/Icone'
import { Marca } from '../../componentes/Marca'
import { ListaConversas } from './ListaConversas'
import estilos from './Chat.module.css'

interface Props {
  aoNavegar?: () => void
  aoFechar?: () => void
}

export function ConteudoLateral({ aoNavegar, aoFechar }: Props) {
  const { novaConversa } = useChat()
  const { pessoa } = usePessoa()

  return (
    <div className={estilos.lateral}>
      <div className={estilos.lateralTopo}>
        <div className={estilos.marcaTopo}>
          <Marca legenda="conversa" />
          {aoFechar ? (
            <button
              type="button"
              className={estilos.botaoIcone}
              onClick={aoFechar}
              aria-label="Fechar conversas"
            >
              <Icone nome="fechar" />
            </button>
          ) : null}
        </div>
        <Botao
          variante="secundario"
          larguraTotal
          className={estilos.novaConversa}
          icone={<Icone nome="mais" tamanho={18} />}
          onClick={() => {
            novaConversa()
            aoNavegar?.()
          }}
        >
          Nova conversa
        </Botao>
      </div>

      <div className={estilos.lista}>
        <ListaConversas aoSelecionar={aoNavegar} />
      </div>

      <div className={estilos.lateralRodape}>
        {pessoa ? (
          <Link to="/conta" className={estilos.pessoa} onClick={() => aoNavegar?.()}>
            <span className={estilos.avatar} aria-hidden="true">
              {iniciais(pessoa.nome)}
            </span>
            <span className={estilos.pessoaTexto}>
              <span className={estilos.pessoaNome}>{pessoa.nome}</span>
              <span className={estilos.pessoaLink}>Conta e ajustes</span>
            </span>
            <Icone nome="conta" tamanho={17} />
          </Link>
        ) : null}
        <BotaoInstalar larguraTotal />
      </div>
    </div>
  )
}
