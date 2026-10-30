import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useSessao } from '../../auth/contexto'
import { usePessoa } from '../../pessoa/contexto'
import { Banner } from '../../componentes/Banner'
import { Botao } from '../../componentes/Botao'
import { Campo } from '../../componentes/Campo'
import { CarregandoTela } from '../../componentes/Carregando'
import { Icone } from '../../componentes/Icone'
import { Marca } from '../../componentes/Marca'
import estilos from './Login.module.css'

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

function mensagemDaUrl(): string | null {
  const params = new URLSearchParams(window.location.search)
  const codigo = params.get('error_code') ?? params.get('error')
  const descricao = params.get('error_description')
  if (!codigo && !descricao) return null
  if (codigo === 'otp_expired' || descricao?.includes('expired')) {
    return 'Esse link expirou. Peça um novo acesso abaixo.'
  }
  return 'Não foi possível concluir a entrada. Peça um novo link.'
}

export function Login() {
  const { sessao, carregando, entrarComEmail, verificarCodigo } = useSessao()
  const { pessoa, carregando: carregandoPessoa } = usePessoa()

  const [etapa, setEtapa] = useState<'email' | 'enviado'>('email')
  const [email, setEmail] = useState('')
  const [codigo, setCodigo] = useState('')
  const [erroInicial] = useState(mensagemDaUrl)
  const [erro, setErro] = useState<string | null>(erroInicial)
  const [enviando, setEnviando] = useState(false)
  const [espera, setEspera] = useState(0)

  useEffect(() => {
    if (erroInicial) {
      window.history.replaceState({}, '', window.location.pathname)
    }
  }, [erroInicial])

  useEffect(() => {
    if (espera <= 0) return
    const temporizador = window.setTimeout(() => setEspera(espera - 1), 1000)
    return () => window.clearTimeout(temporizador)
  }, [espera])

  if (carregando) return <CarregandoTela />
  if (sessao && carregandoPessoa) return <CarregandoTela texto="Entrando…" />
  if (sessao && pessoa) return <Navigate to="/" replace />
  if (sessao) return <Navigate to="/onboarding" replace />

  const enviarLink = async (evento?: React.FormEvent) => {
    evento?.preventDefault()
    const limpo = email.trim().toLowerCase()
    if (!EMAIL.test(limpo)) {
      setErro('Digite um e-mail válido, como nome@exemplo.com.')
      return
    }
    setEnviando(true)
    setErro(null)
    try {
      await entrarComEmail(limpo)
      setEmail(limpo)
      setEtapa('enviado')
      setEspera(60)
    } catch (falha) {
      setErro(
        falha instanceof Error ? falha.message : 'Não foi possível enviar o link.',
      )
    } finally {
      setEnviando(false)
    }
  }

  const entrarComCodigo = async (evento: React.FormEvent) => {
    evento.preventDefault()
    if (!/^\d{6}$/.test(codigo.trim())) {
      setErro('O código tem 6 dígitos.')
      return
    }
    setEnviando(true)
    setErro(null)
    try {
      await verificarCodigo(email, codigo)
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : 'Código inválido.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className={estilos.pagina}>
      <aside className={estilos.marca}>
        <Marca clara legenda="conversa" />
        <div className={estilos.frase}>
          <p className={estilos.olho}>Um lugar calmo</p>
          <h1>Para falar do dia, lembrar de coisas e pensar em voz alta.</h1>
          <p>
            Conversas só suas, sem senha e sem pressa. A Sera escuta, responde e lembra
            do que importa para você.
          </p>
        </div>
        <div className={estilos.selo}>
          <Icone nome="escudo" tamanho={17} />
          <span>Suas conversas ficam entre você e a Sera.</span>
        </div>
      </aside>

      <main className={estilos.painel} id="conteudo">
        <div className={estilos.cartao}>
          <div className={estilos.marcaMobile}>
            <Marca />
          </div>

          {etapa === 'email' ? (
            <>
              <h1 className={estilos.titulo}>Entrar</h1>
              <p className={estilos.subtitulo}>
                Digite seu e-mail. A gente envia um link de acesso — não precisa de
                senha.
              </p>
              <form className={estilos.formulario} onSubmit={enviarLink} noValidate>
                {erro ? <Banner tipo="erro">{erro}</Banner> : null}
                <Campo
                  rotulo="E-mail"
                  type="email"
                  inputMode="email"
                  autoComplete="email"
                  placeholder="voce@exemplo.com"
                  value={email}
                  onChange={(evento) => setEmail(evento.target.value)}
                  required
                />
                <Botao
                  type="submit"
                  larguraTotal
                  carregando={enviando}
                  disabled={!email.trim()}
                >
                  Receber link de acesso
                </Botao>
              </form>
            </>
          ) : (
            <>
              <h1 className={estilos.titulo}>Confira seu e-mail</h1>
              <p className={estilos.subtitulo}>
                Enviamos um acesso para{' '}
                <span className={estilos.destaque}>{email}</span>. Abra o link no mesmo
                aparelho em que você está agora.
              </p>

              {erro ? <Banner tipo="erro">{erro}</Banner> : null}

              <form
                className={estilos.formulario}
                onSubmit={entrarComCodigo}
                noValidate
              >
                <Campo
                  rotulo="Código de 6 dígitos"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  pattern="\d{6}"
                  maxLength={6}
                  placeholder="000000"
                  value={codigo}
                  onChange={(evento) =>
                    setCodigo(evento.target.value.replace(/\D/g, ''))
                  }
                  dica="Se o e-mail mostrar um código em vez do link, digite aqui."
                />
                <Botao
                  type="submit"
                  larguraTotal
                  carregando={enviando}
                  disabled={codigo.length !== 6}
                >
                  Entrar com código
                </Botao>
              </form>

              <div className={estilos.acoesSecundarias}>
                <button
                  type="button"
                  className={estilos.link}
                  onClick={() => void enviarLink()}
                  disabled={espera > 0 || enviando}
                >
                  {espera > 0 ? `Reenviar acesso em ${espera}s` : 'Reenviar acesso'}
                </button>
                <button
                  type="button"
                  className={estilos.link}
                  onClick={() => {
                    setEtapa('email')
                    setCodigo('')
                    setErro(null)
                  }}
                >
                  Usar outro e-mail
                </button>
              </div>
            </>
          )}

          <p className={estilos.rodape}>
            A Sera é uma IA, não substitui ajuda humana. Em emergências, ligue 192
            (SAMU) ou 188 (CVV).
          </p>
        </div>
      </main>
    </div>
  )
}
