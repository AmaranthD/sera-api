import { Botao } from './Botao'
import { Icone } from './Icone'
import { useInstalacao } from '../pwa/usePwa'
import estilos from './BotaoInstalar.module.css'

export function BotaoInstalar({ larguraTotal = false }: { larguraTotal?: boolean }) {
  const { podeInstalar, instalado, ehIOS, instalar } = useInstalacao()

  if (instalado || (!podeInstalar && !ehIOS)) return null

  if (!podeInstalar && ehIOS) {
    return (
      <div className={estilos.instrucao}>
        <strong>Instalar no iPhone:</strong> toque em Compartilhar e depois em
        “Adicionar à Tela de Início”.
      </div>
    )
  }

  return (
    <Botao
      variante="secundario"
      larguraTotal={larguraTotal}
      icone={<Icone nome="instalar" tamanho={18} />}
      onClick={() => void instalar()}
    >
      Instalar app
    </Botao>
  )
}
