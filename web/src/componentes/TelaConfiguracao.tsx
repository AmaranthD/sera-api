import { ErroConfiguracao } from '../env'
import { Marca } from './Marca'
import estilos from './TelaConfiguracao.module.css'

export function TelaConfiguracao({ erro }: { erro: unknown }) {
  const campos =
    erro instanceof ErroConfiguracao ? erro.campos : ['configuração do build']

  return (
    <div className={estilos.pagina}>
      <div className={estilos.cartao}>
        <Marca legenda="configuração" />
        <h1 className={estilos.titulo}>Falta configurar o app.</h1>
        <p className={estilos.texto}>
          O build precisa de três variáveis públicas. Crie o arquivo{' '}
          <code>web/.env.local</code> (ou preencha no Cloudflare Pages) com:
        </p>
        <ul className={estilos.lista}>
          {campos.map((campo) => (
            <li key={campo}>{campo}</li>
          ))}
        </ul>
        <pre className={estilos.codigo}>
          {`VITE_SUPABASE_URL=https://<ref>.supabase.co
VITE_SUPABASE_ANON_KEY=<publishable/anon key>
VITE_API_URL=https://<api>.onrender.com`}
        </pre>
        <p className={estilos.nota}>
          A chave <strong>anon/publishable</strong> é pública por desenho. Nunca coloque{' '}
          <code>service_role</code>, <code>LLM_API_KEY</code> ou senha do banco no
          front.
        </p>
      </div>
    </div>
  )
}
