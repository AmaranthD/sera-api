import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import type { ApiSera } from '../../api/sera'
import { ehSessaoExpirada, mensagemDoErro } from '../../api/erros'
import { Banner } from '../../componentes/Banner'
import { Botao } from '../../componentes/Botao'
import { Campo } from '../../componentes/Campo'
import { Icone } from '../../componentes/Icone'
import type { AssinaturaTextoDiario } from '../../dominios/tipos'
import estilos from './Conta.module.css'

interface Props {
  pessoaId: string
  api: ApiSera
  sair: () => Promise<void>
}

function fusoDoNavegador(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone
  } catch {
    return 'America/Sao_Paulo'
  }
}

function zonasDisponiveis(): string[] {
  const navegador = fusoDoNavegador()
  try {
    const zonas = Intl.supportedValuesOf('timeZone')
    return zonas.includes(navegador) ? zonas : [navegador, ...zonas]
  } catch {
    return [navegador]
  }
}

export function SecaoTextoDiario({ pessoaId, api, sair }: Props) {
  const [assinatura, setAssinatura] = useState<AssinaturaTextoDiario | null>(null)
  const [ativo, setAtivo] = useState(false)
  const [hora, setHora] = useState('07:00')
  const [fuso, setFuso] = useState(fusoDoNavegador)
  const [carregando, setCarregando] = useState(true)
  const [salvando, setSalvando] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const [ultimaConversa, setUltimaConversa] = useState<string | null>(null)
  const zonas = useMemo(() => zonasDisponiveis(), [])
  const opcoesFuso = zonas.includes(fuso) ? zonas : [fuso, ...zonas]

  useEffect(() => {
    let ativoNaTela = true
    setCarregando(true)
    setErro(null)
    api
      .obterTextoDiario(pessoaId)
      .then((dados) => {
        if (!ativoNaTela) return
        setAssinatura(dados)
        setAtivo(dados.ativo)
        setHora(dados.hora || '07:00')
        setFuso(dados.fuso || fusoDoNavegador())
      })
      .catch(async (falha) => {
        if (!ativoNaTela) return
        if (ehSessaoExpirada(falha)) {
          await sair()
          return
        }
        setErro(mensagemDoErro(falha))
      })
      .finally(() => {
        if (ativoNaTela) setCarregando(false)
      })
    return () => {
      ativoNaTela = false
    }
  }, [api, pessoaId, sair])

  async function salvar(evento: React.FormEvent) {
    evento.preventDefault()
    const horaNormalizada = hora.slice(0, 5)
    if (!horaNormalizada) {
      setErro('Escolha um horário para o envio.')
      return
    }
    setSalvando(true)
    setErro(null)
    setAviso(null)
    try {
      const dados = await api.salvarTextoDiario(pessoaId, {
        ativo,
        hora: horaNormalizada,
        fuso: fuso || fusoDoNavegador(),
      })
      setAssinatura(dados)
      setAviso(
        dados.ativo
          ? `Texto diário ativado para ${dados.hora}.`
          : 'Envio diário desativado.',
      )
    } catch (falha) {
      if (ehSessaoExpirada(falha)) {
        await sair()
        return
      }
      setErro(mensagemDoErro(falha))
    } finally {
      setSalvando(false)
    }
  }

  async function enviarAgora() {
    setEnviando(true)
    setErro(null)
    setAviso(null)
    try {
      const entrega = await api.enviarTextoDiarioAgora(pessoaId)
      setUltimaConversa(entrega.conversa_id)
      setAviso(`Texto de ${entrega.dia} enviado na conversa “Texto diário”.`)
    } catch (falha) {
      if (ehSessaoExpirada(falha)) {
        await sair()
        return
      }
      setErro(mensagemDoErro(falha))
    } finally {
      setEnviando(false)
    }
  }

  if (carregando) {
    return (
      <section className={estilos.secao} aria-labelledby="texto-diario-titulo">
        <h2 className={estilos.secaoTitulo} id="texto-diario-titulo">
          Texto diário
        </h2>
        <p className={estilos.secaoTexto}>Carregando sua configuração…</p>
      </section>
    )
  }

  return (
    <section className={estilos.secao} aria-labelledby="texto-diario-titulo">
      <h2 className={estilos.secaoTitulo} id="texto-diario-titulo">
        Texto diário
      </h2>
      <p className={estilos.secaoTexto}>
        Receba o texto diário das Testemunhas de Jeová todo dia no horário que você
        escolher. Ele vai para uma conversa chamada “Texto diário”, com links que abrem
        o conteúdo ali mesmo.
      </p>

      {erro ? <Banner tipo="erro">{erro}</Banner> : null}
      {aviso ? (
        <Banner tipo="sucesso">
          {aviso}
          {ultimaConversa ? (
            <>
              {' '}
              <Link className={estilos.linkAviso} to={`/c/${ultimaConversa}`}>
                Abrir conversa
              </Link>
            </>
          ) : null}
        </Banner>
      ) : null}

      <form className={estilos.textoDiarioForm} onSubmit={(e) => void salvar(e)}>
        <label className={estilos.alternador}>
          <input
            type="checkbox"
            checked={ativo}
            onChange={(evento) => setAtivo(evento.target.checked)}
          />
          <span>
            <strong>Enviar todos os dias</strong>
            <span className={estilos.alternadorAjuda}>
              {assinatura?.ultimo_envio_dia
                ? `Último envio: ${assinatura.ultimo_envio_dia}`
                : 'Ainda não enviado'}
            </span>
          </span>
        </label>

        <div className={estilos.duasColunasConta}>
          <Campo
            rotulo="Horário"
            type="time"
            value={hora}
            onChange={(evento) => setHora(evento.target.value)}
            required
          />
          {zonas.length > 1 ? (
            <label className={estilos.rotuloArea}>
              <span>Fuso horário</span>
              <select
                className={estilos.area}
                value={fuso}
                onChange={(evento) => setFuso(evento.target.value)}
              >
                {opcoesFuso.map((zona) => (
                  <option key={zona} value={zona}>
                    {zona}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <Campo
              rotulo="Fuso horário"
              value={fuso}
              onChange={(evento) => setFuso(evento.target.value)}
            />
          )}
        </div>

        <div className={estilos.acoes}>
          <Botao type="submit" carregando={salvando}>
            Salvar texto diário
          </Botao>
          <Botao
            type="button"
            variante="secundario"
            carregando={enviando}
            icone={<Icone nome="alerta" tamanho={16} />}
            onClick={() => void enviarAgora()}
          >
            Enviar agora
          </Botao>
        </div>
      </form>

      <p className={estilos.nota}>
        O aviso no celular ou computador depende das notificações ativadas na{' '}
        <Link className={estilos.linkAviso} to="/agenda">
          Agenda
        </Link>
        . O texto continua disponível na conversa mesmo sem notificação.
      </p>
    </section>
  )
}
