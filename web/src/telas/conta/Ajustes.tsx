import { useState, type FormEvent } from 'react'
import { mensagemDoErro } from '../../api/erros'
import { Banner } from '../../componentes/Banner'
import { Botao } from '../../componentes/Botao'
import type { Ajuste, AtualizacaoAjuste, TipoAjuste } from '../../dominios/tipos'
import estilos from './Conta.module.css'

const ROTULO_TIPO: Record<TipoAjuste, string> = {
  apelido: 'Apelido',
  piada_interna: 'Piada interna',
  formato: 'Preferência de formato',
  assunto: 'Assunto favorito',
  nivel_sarcasmo: 'Nível de sarcasmo',
  formalidade: 'Formalidade',
  nivel_tecnico: 'Nível técnico',
  toque_yandere: 'Toque dramático',
}

const VALORES: Partial<Record<TipoAjuste, readonly string[]>> = {
  nivel_sarcasmo: ['nenhum', 'leve', 'medio', 'alto'],
  formalidade: ['baixa', 'media', 'alta'],
  nivel_tecnico: ['baixo', 'medio', 'alto'],
  toque_yandere: ['desligado', 'leve', 'medio'],
}

const ROTULO_VALOR: Record<string, string> = {
  nenhum: 'nenhum',
  leve: 'leve',
  medio: 'médio',
  alto: 'alto',
  baixa: 'baixa',
  media: 'média',
  alta: 'alta',
  baixo: 'baixo',
  desligado: 'desligado',
}

interface Props {
  ajustes: Ajuste[]
  carregando: boolean
  erro: string | null
  aoAtualizar: (id: string, dados: AtualizacaoAjuste) => Promise<void>
  aoApagar: (id: string) => Promise<void>
  aoTentarDeNovo: () => void
}

function valorEditavel(ajuste: Ajuste): string {
  return ajuste.texto ?? ajuste.valor ?? ''
}

function valorExibido(ajuste: Ajuste): string {
  if (ajuste.texto) return ajuste.texto
  if (ajuste.valor) return ROTULO_VALOR[ajuste.valor] ?? ajuste.valor
  return '—'
}

export function SecaoAjustes({
  ajustes,
  carregando,
  erro,
  aoAtualizar,
  aoApagar,
  aoTentarDeNovo,
}: Props) {
  const [editandoId, setEditandoId] = useState<string | null>(null)
  const [rascunho, setRascunho] = useState('')
  const [salvando, setSalvando] = useState(false)
  const [confirmandoId, setConfirmandoId] = useState<string | null>(null)
  const [apagandoId, setApagandoId] = useState<string | null>(null)
  const [erroLocal, setErroLocal] = useState<string | null>(null)

  function comecarEdicao(ajuste: Ajuste) {
    setEditandoId(ajuste.id)
    setRascunho(valorEditavel(ajuste))
    setConfirmandoId(null)
    setErroLocal(null)
  }

  function cancelarEdicao() {
    setEditandoId(null)
    setErroLocal(null)
  }

  async function salvar(evento: FormEvent) {
    evento.preventDefault()
    const ajuste = ajustes.find((item) => item.id === editandoId)
    if (!ajuste || !rascunho.trim()) return

    setSalvando(true)
    setErroLocal(null)
    try {
      const dados: AtualizacaoAjuste = VALORES[ajuste.tipo]
        ? { valor: rascunho.trim() }
        : { texto: rascunho.trim() }
      await aoAtualizar(ajuste.id, dados)
      setEditandoId(null)
    } catch (falha) {
      setErroLocal(mensagemDoErro(falha))
    } finally {
      setSalvando(false)
    }
  }

  async function apagar(id: string) {
    setApagandoId(id)
    setErroLocal(null)
    try {
      await aoApagar(id)
      setConfirmandoId(null)
    } catch (falha) {
      setErroLocal(mensagemDoErro(falha))
    } finally {
      setApagandoId(null)
    }
  }

  return (
    <section className={estilos.secao} aria-labelledby="ajustes-titulo">
      <div className={estilos.secaoTopo}>
        <h2 className={estilos.secaoTitulo} id="ajustes-titulo">
          Ajustes aprendidos
        </h2>
        {!carregando && ajustes.length > 0 ? (
          <span className={estilos.chip}>{ajustes.length}/20</span>
        ) : null}
      </div>
      <p className={estilos.secaoTexto}>
        Preferências que mudam o jeito da Sera conversar com você.
      </p>

      {erro ? (
        <Banner
          tipo="erro"
          acao={{ rotulo: 'Tentar de novo', aoClicar: aoTentarDeNovo }}
        >
          {erro}
        </Banner>
      ) : null}
      {erroLocal ? <Banner tipo="erro">{erroLocal}</Banner> : null}
      {carregando ? <p className={estilos.vazio}>Carregando…</p> : null}

      {!carregando && !erro && ajustes.length === 0 ? (
        <p className={estilos.vazio}>
          Nenhum ajuste ainda. Na conversa, peça “me chame de…” ou “fale de um jeito
          menos formal”.
        </p>
      ) : null}

      <ul className={estilos.lista}>
        {ajustes.map((ajuste) => {
          const opcoes = VALORES[ajuste.tipo]
          return (
            <li className={estilos.item} key={ajuste.id}>
              {editandoId === ajuste.id ? (
                <form className={estilos.formulario} onSubmit={salvar}>
                  <label
                    className={estilos.campoRotulo}
                    htmlFor={`ajuste-${ajuste.id}`}
                  >
                    {ROTULO_TIPO[ajuste.tipo]}
                  </label>
                  {opcoes ? (
                    <select
                      id={`ajuste-${ajuste.id}`}
                      className={estilos.select}
                      value={rascunho}
                      onChange={(evento) => setRascunho(evento.target.value)}
                    >
                      {opcoes.map((valor) => (
                        <option key={valor} value={valor}>
                          {ROTULO_VALOR[valor] ?? valor}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      id={`ajuste-${ajuste.id}`}
                      className={estilos.input}
                      value={rascunho}
                      onChange={(evento) => setRascunho(evento.target.value)}
                      maxLength={200}
                    />
                  )}
                  <div className={estilos.acoesInline}>
                    <Botao
                      type="submit"
                      className={estilos.botaoPequeno}
                      carregando={salvando}
                      disabled={!rascunho.trim()}
                    >
                      Salvar
                    </Botao>
                    <Botao
                      type="button"
                      variante="fantasma"
                      className={estilos.botaoPequeno}
                      onClick={cancelarEdicao}
                    >
                      Cancelar
                    </Botao>
                  </div>
                </form>
              ) : (
                <>
                  <div className={estilos.itemConteudo}>
                    <div className={estilos.ajusteTexto}>
                      <span className={estilos.ajusteRotulo}>
                        {ROTULO_TIPO[ajuste.tipo]}
                      </span>
                      <span className={estilos.itemTexto}>{valorExibido(ajuste)}</span>
                    </div>
                  </div>
                  <div className={estilos.itemAcoes}>
                    <Botao
                      variante="fantasma"
                      className={estilos.botaoPequeno}
                      aria-label={`Editar ajuste: ${ROTULO_TIPO[ajuste.tipo]}`}
                      onClick={() => comecarEdicao(ajuste)}
                    >
                      Editar
                    </Botao>
                    <Botao
                      variante="fantasma"
                      className={estilos.botaoPequeno}
                      aria-label={`Apagar ajuste: ${ROTULO_TIPO[ajuste.tipo]}`}
                      onClick={() => {
                        setConfirmandoId(ajuste.id)
                        setErroLocal(null)
                      }}
                    >
                      Apagar
                    </Botao>
                  </div>
                </>
              )}

              {confirmandoId === ajuste.id ? (
                <div className={estilos.confirmacao} role="alert">
                  <p className={estilos.confirmacaoTexto}>
                    Apagar este ajuste? A Sera volta ao jeito padrão nesse ponto.
                  </p>
                  <div className={estilos.acoesInline}>
                    <Botao
                      variante="perigo"
                      className={estilos.botaoPequeno}
                      carregando={apagandoId === ajuste.id}
                      onClick={() => void apagar(ajuste.id)}
                    >
                      Sim, apagar
                    </Botao>
                    <Botao
                      variante="fantasma"
                      className={estilos.botaoPequeno}
                      onClick={() => setConfirmandoId(null)}
                    >
                      Cancelar
                    </Botao>
                  </div>
                </div>
              ) : null}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
