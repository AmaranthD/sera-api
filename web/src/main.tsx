import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/cinzel/latin-ext-400.css'
import '@fontsource/cinzel/latin-ext-600.css'
import '@fontsource/silkscreen/latin-ext-400.css'
import '@fontsource/silkscreen/latin-ext-700.css'
import { App } from './App'
import { LimiteDeErro } from './componentes/LimiteDeErro'
import { TelaConfiguracao } from './componentes/TelaConfiguracao'
import { lerAmbiente } from './env'
import './estilos/global.css'

const elemento = document.getElementById('root')
if (!elemento) throw new Error('Elemento #root não encontrado.')

const raiz = createRoot(elemento)

try {
  const ambiente = lerAmbiente()
  raiz.render(
    <StrictMode>
      <LimiteDeErro>
        <App ambiente={ambiente} />
      </LimiteDeErro>
    </StrictMode>,
  )
} catch (erro) {
  raiz.render(<TelaConfiguracao erro={erro} />)
}
