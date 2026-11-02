import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { mensagemDoErro, ehSessaoExpirada } from '../../api/erros'
import { useSessao } from '../../auth/contexto'
import { Banner } from '../../componentes/Banner'
import { Botao } from '../../componentes/Botao'
import { Campo } from '../../componentes/Campo'
import { CarregandoLinha, CarregandoTela } from '../../componentes/Carregando'
import { Icone } from '../../componentes/Icone'
import { Marca } from '../../componentes/Marca'
import type { Compromisso, EntradaCompromisso } from '../../dominios/tipos'
import {
  ativarPush,
  desativarPush,
  estadoPush,
  pushSuportado,
  type EstadoPush,
} from '../../notificacoes/push'
import { useInstalacao } from '../../pwa/usePwa'
import { usePessoa } from '../../pessoa/contexto'
import { formatarDiaLongo, formatarHora } from '../../dominios/texto'
import {
  LEMBRETES,
  deEntradaLocal,
  fimPadrao,
  novoFormulario,
  paraEntradaLocal,
  rotuloLembrete,
  type Formulario,
} from './formulario'
import estilos from './Agenda.module.css'

export function Agenda() {
  const { api, sair } = useSessao()
  const { pessoa, carregando: carregandoPessoa } = usePessoa()
  const { instalado, ehIOS } = useInstalacao()

  const [compromissos, setCompromissos] = useState<Compromisso[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const [salvando, setSalvando] = useState(false)
  const [editando, setEditando] = useState<string | null>(null)
  const [formulario, setFormulario] = useState<Formulario>(novoFormulario)
  const [estadoNotif, setEstadoNotif] = useState<EstadoPush>('inativo')
  const [mexendoNotif, setMexendoNotif] = useState(false)
  const [referencia, setReferencia] = useState(0)

  const carregar = useCallback(async () => {
    if (!pessoa) return
    setCarregando(true)
    setErro(null)
    try {
      setCompromissos(await api.listarCompromissos(pessoa.id))
    } catch (falha) {
      if (ehSessaoExpirada(falha)) {
        await sair()
        return
      }
      setErro(mensagemDoErro(falha))
    } finally {
      setCarregando(false)
    }
  }, [api, pessoa, sair])

  useEffect(() => {
    void carregar()
  }, [carregar])

  useEffect(() => {
    let ativo = true
    void estadoPush().then((estado) => {
      if (ativo) setEstadoNotif(estado)
    })
    return () => {
      ativo = false
    }
  }, [])

  useEffect(() => {
    const atualizar = () => setReferencia(Date.now())
    atualizar()
    const temporizador = window.setInterval(atualizar, 60_000)
    return () => window.clearInterval(temporizador)
  }, [])

  const futuros = useMemo(
    () =>
      [...compromissos]
        .filter((item) => new Date(item.fim).getTime() >= referencia)
        .sort((a, b) => new Date(a.inicio).getTime() - new Date(b.inicio).getTime()),
    [compromissos, referencia],
  )

  const dias = useMemo(() => {
    const mapa = new Map<string, Compromisso[]>()
    for (const item of futuros) {
      const chave = new Date(item.inicio).toDateString()
      const lista = mapa.get(chave) ?? []
      lista.push(item)
      mapa.set(chave, lista)
    }
    return [...mapa.entries()]
  }, [futuros])

  function limparFormulario() {
    setEditando(null)
    setFormulario(novoFormulario())
  }

  function editar(item: Compromisso) {
    setEditando(item.id)
    setErro(null)
    setAviso(null)
    setFormulario({
      titulo: item.titulo,
      descricao: item.descricao,
      inicio: paraEntradaLocal(item.inicio),
      fim: paraEntradaLocal(item.fim),
      lembrete: item.lembrete_minutos,
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function salvar(evento: React.FormEvent) {
    evento.preventDefault()
    if (!pessoa) return
    const titulo = formulario.titulo.trim()
    if (!titulo) {
      setErro('Dê um nome para o compromisso.')
      return
    }
    if (new Date(formulario.fim) <= new Date(formulario.inicio)) {
      setErro('O fim precisa ser depois do início.')
      return
    }

    const dados: EntradaCompromisso = {
      titulo,
      descricao: formulario.descricao.trim(),
      inicio: deEntradaLocal(formulario.inicio),
      fim: deEntradaLocal(formulario.fim),
      fuso: Intl.DateTimeFormat().resolvedOptions().timeZone,
      lembrete_minutos: formulario.lembrete,
    }

    setSalvando(true)
    setErro(null)
    setAviso(null)
    try {
      if (editando) {
        const atualizado = await api.atualizarCompromisso(pessoa.id, editando, dados)
        setCompromissos((atuais) =>
          atuais.map((item) => (item.id === editando ? atualizado : item)),
        )
        setAviso('Compromisso atualizado.')
      } else {
        const criado = await api.criarCompromisso(pessoa.id, dados)
        setCompromissos((atuais) => [...atuais, criado])
        setAviso('Compromisso agendado.')
      }
      limparFormulario()
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

  async function apagar(item: Compromisso) {
    if (!pessoa) return
    if (!window.confirm(`Apagar “${item.titulo}”?`)) return
    try {
      await api.apagarCompromisso(pessoa.id, item.id)
      setCompromissos((atuais) => atuais.filter((outro) => outro.id !== item.id))
      if (editando === item.id) limparFormulario()
      setAviso('Compromisso apagado.')
    } catch (falha) {
      if (ehSessaoExpirada(falha)) {
        await sair()
        return
      }
      setErro(mensagemDoErro(falha))
    }
  }

  async function alternarNotificacoes() {
    if (!pessoa) return
    setMexendoNotif(true)
    setErro(null)
    setAviso(null)
    try {
      const novo =
        estadoNotif === 'ativo'
          ? await desativarPush(api, pessoa.id)
          : await ativarPush(api, pessoa.id)
      setEstadoNotif(novo)
      if (novo === 'ativo') {
        setAviso('Notificações ativadas neste dispositivo.')
      } else if (novo === 'negado') {
        setErro('O navegador bloqueou as notificações. Libere nas permissões do site.')
      }
    } catch (falha) {
      if (ehSessaoExpirada(falha)) {
        await sair()
        return
      }
      setErro(mensagemDoErro(falha))
    } finally {
      setMexendoNotif(false)
    }
  }

  async function testarNotificacao() {
    if (!pessoa) return
    setMexendoNotif(true)
    setErro(null)
    setAviso(null)
    try {
      const resultado = await api.testarNotificacao(pessoa.id)
      setAviso(
        `Notificação enviada para ${resultado.enviados} de ${resultado.dispositivos} dispositivo(s).`,
      )
    } catch (falha) {
      if (ehSessaoExpirada(falha)) {
        await sair()
        return
      }
      setErro(mensagemDoErro(falha))
    } finally {
      setMexendoNotif(false)
    }
  }

  if (carregandoPessoa) return <CarregandoTela />
  if (!pessoa) return <Navigate to="/onboarding" replace />

  const rotuloNotificacao =
    estadoNotif === 'ativo' ? 'Desativar neste dispositivo' : 'Ativar notificações'

  return (
    <div className={estilos.pagina}>
      <header className={estilos.topo}>
        <Marca pequena legenda="agenda" />
        <Link to="/" className={estilos.voltar}>
          <Icone nome="voltar" tamanho={17} />
          Voltar para a conversa
        </Link>
      </header>

      <main className={estilos.conteudo} id="conteudo">
        <section className={estilos.cartao}>
          <h1 className={estilos.titulo}>Sua agenda</h1>
          <p className={estilos.subtitulo}>
            Marque compromissos e receba um aviso no computador e no celular. Dois
            compromissos não podem ocupar o mesmo horário.
          </p>

          {estadoNotif === 'nao_suportado' ? (
            <Banner tipo="aviso">
              Este navegador não aceita notificações. No iPhone, instale a Sera na tela
              inicial primeiro.
            </Banner>
          ) : estadoNotif === 'negado' ? (
            <Banner tipo="aviso">
              As notificações estão bloqueadas para este site. Libere nas permissões do
              navegador e recarregue a página.
            </Banner>
          ) : estadoNotif === 'inativo' && ehIOS && !instalado ? (
            <Banner tipo="aviso">
              No iPhone, as notificações só funcionam com a Sera instalada na tela
              inicial.
            </Banner>
          ) : null}

          {pushSuportado() ? (
            <div className={estilos.notificacoes}>
              <Botao
                variante={estadoNotif === 'ativo' ? 'secundario' : 'primario'}
                carregando={mexendoNotif}
                onClick={() => void alternarNotificacoes()}
                icone={<Icone nome="alerta" tamanho={17} />}
              >
                {rotuloNotificacao}
              </Botao>
              {estadoNotif === 'ativo' ? (
                <Botao
                  variante="fantasma"
                  carregando={mexendoNotif}
                  onClick={() => void testarNotificacao()}
                >
                  Enviar teste
                </Botao>
              ) : null}
            </div>
          ) : null}
        </section>

        {erro ? <Banner tipo="erro">{erro}</Banner> : null}
        {aviso ? <Banner tipo="sucesso">{aviso}</Banner> : null}

        <section className={estilos.cartao}>
          <h2 className={estilos.tituloSecao}>
            {editando ? 'Editar compromisso' : 'Novo compromisso'}
          </h2>
          <form className={estilos.formulario} onSubmit={(e) => void salvar(e)}>
            <Campo
              rotulo="Título"
              value={formulario.titulo}
              maxLength={120}
              placeholder="Consulta, reunião, aniversário..."
              onChange={(evento) =>
                setFormulario((atual) => ({
                  ...atual,
                  titulo: evento.target.value,
                }))
              }
              required
            />

            <label className={estilos.rotuloArea}>
              <span>Detalhes (opcional)</span>
              <textarea
                className={estilos.area}
                value={formulario.descricao}
                maxLength={2000}
                onChange={(evento) =>
                  setFormulario((atual) => ({
                    ...atual,
                    descricao: evento.target.value,
                  }))
                }
              />
            </label>

            <div className={estilos.duasColunas}>
              <Campo
                rotulo="Começa em"
                type="datetime-local"
                value={formulario.inicio}
                onChange={(evento) => {
                  const inicio = evento.target.value
                  setFormulario((atual) => ({
                    ...atual,
                    inicio,
                    fim:
                      new Date(atual.fim) <= new Date(inicio)
                        ? fimPadrao(inicio)
                        : atual.fim,
                  }))
                }}
                required
              />
              <Campo
                rotulo="Termina em"
                type="datetime-local"
                value={formulario.fim}
                onChange={(evento) =>
                  setFormulario((atual) => ({
                    ...atual,
                    fim: evento.target.value,
                  }))
                }
                required
              />
            </div>

            <label className={estilos.rotuloArea}>
              <span>Lembrete</span>
              <select
                className={estilos.area}
                value={formulario.lembrete}
                onChange={(evento) =>
                  setFormulario((atual) => ({
                    ...atual,
                    lembrete: Number(evento.target.value),
                  }))
                }
              >
                {LEMBRETES.map((minutos) => (
                  <option key={minutos} value={minutos}>
                    {rotuloLembrete(minutos)}
                  </option>
                ))}
              </select>
            </label>

            <div className={estilos.acoesFormulario}>
              <Botao type="submit" carregando={salvando}>
                {editando ? 'Salvar alterações' : 'Agendar'}
              </Botao>
              {editando ? (
                <Botao variante="fantasma" onClick={limparFormulario}>
                  Cancelar
                </Botao>
              ) : null}
            </div>
          </form>
        </section>

        <section className={estilos.cartao}>
          <h2 className={estilos.tituloSecao}>Próximos compromissos</h2>
          {carregando ? (
            <CarregandoLinha texto="Carregando sua agenda" />
          ) : dias.length === 0 ? (
            <p className={estilos.vazio}>
              Nada marcado por enquanto. Crie o primeiro compromisso acima.
            </p>
          ) : (
            <div className={estilos.dias}>
              {dias.map(([chave, itens]) => (
                <div key={chave} className={estilos.dia}>
                  <h3 className={estilos.diaTitulo}>
                    {itens[0] ? formatarDiaLongo(itens[0].inicio) : ''}
                  </h3>
                  <ul className={estilos.lista}>
                    {itens.map((item) => (
                      <li key={item.id} className={estilos.item}>
                        <div className={estilos.horario}>
                          {formatarHora(item.inicio)}
                          <span>{formatarHora(item.fim)}</span>
                        </div>
                        <div className={estilos.itemTexto}>
                          <strong>{item.titulo}</strong>
                          {item.descricao ? <p>{item.descricao}</p> : null}
                          <span className={estilos.lembrete}>
                            <Icone nome="relogio" tamanho={13} />
                            {rotuloLembrete(item.lembrete_minutos)}
                          </span>
                        </div>
                        <div className={estilos.itemAcoes}>
                          <button
                            type="button"
                            className={estilos.acao}
                            onClick={() => editar(item)}
                          >
                            Editar
                          </button>
                          <button
                            type="button"
                            className={`${estilos.acao} ${estilos.acaoPerigo}`}
                            onClick={() => void apagar(item)}
                          >
                            Apagar
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
