import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Banner } from './Banner'
import { Botao } from './Botao'
import { Marca } from './Marca'
import estilos from './LimiteDeErro.module.css'

interface Props {
  children: ReactNode
}

interface State {
  erro: Error | null
}

export class LimiteDeErro extends Component<Props, State> {
  state: State = { erro: null }

  static getDerivedStateFromError(erro: Error): State {
    return { erro }
  }

  componentDidCatch(erro: Error, informacao: ErrorInfo) {
    console.error('Erro não tratado na Sera:', erro, informacao)
  }

  render() {
    if (!this.state.erro) return this.props.children
    return (
      <div className={estilos.pagina}>
        <div className={estilos.cartao}>
          <Marca legenda="ops" />
          <h1 className={estilos.titulo}>Alguma coisa saiu do lugar.</h1>
          <p className={estilos.texto}>
            A conversa continua salva. Recarregue a página para voltar.
          </p>
          <Banner tipo="erro">
            Se continuar acontecendo, feche e abra o app de novo.
          </Banner>
          <Botao
            larguraTotal
            onClick={() => window.location.reload()}
            className={estilos.recarregar}
          >
            Recarregar
          </Botao>
        </div>
      </div>
    )
  }
}
