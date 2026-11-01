import { useState, type FormEvent } from 'react'
import { mensagemDoErro } from '../../api/erros'
import { Banner } from '../../componentes/Banner'
import { Botao } from '../../componentes/Botao'
import type {
  AtualizacaoMemoria,
  CategoriaMemoria,
  Memoria,
} from '../../dominios/tipos'
import estilos from './Conta.module.css'

const ROTULO_CATEGORIA: Record<CategoriaMemoria, string> = {
  familia: 'Família',
  trabalho: 'Trabalho',
  gostos: 'Gostos',
  rotina: 'Rotina',
  saude: 'Saúde',
  outro: 'Outro',
}

const CATEGORIAS = Object.keys(ROTULO_CATEGORIA) as CategoriaMemoria[]

interface Props {
  memorias: Memoria[]
  carregando: boolean
  erro: string | null
  aoAtualizar: (id: string, dados: AtualizacaoMemoria) => Promise<void>
  aoApagar: (id: string) => Promise<void>
  aoTentarDeNovo: () => void
}

export function SecaoMemorias({
  memorias,
  carregando,
  erro,
  aoAtualizar,
  aoApagar,
  aoTentarDeNovo,
}: Props) {
  const [editandoId, setEditandoId] = useState<string | null>(null)
  const [texto, setTexto] = useState('')
  const [categoria, setCategoria] = useState<CategoriaMemoria>('outro')
  const [salvando, setSalvando] = useState(false)
  const [confirmandoId, setConfirmandoId] = useState<string | null>(null)
  const [apagandoId, setApagandoId] = useState<string | null>(null)
  const [erroLocal, setErroLocal] = useState<string | null>(null)

  function comecarEdicao(memoria: Memoria) {
    setEditandoId(memoria.id)
    setTexto(memoria.texto)
    setCategoria(memoria.categoria)
    setConfirmandoId(null)
    setErroLocal(null)
  }

  function cancelarEdicao() {
    setEditandoId(null)
    setErroLocal(null)
  }

  async function salvar(evento: FormEvent) {
    evento.preventDefault()
    if (editandoId === null || !texto.trim()) return
    setSalvando(true)
    setErroLocal(null)
    try {
      await aoAtualizar(editandoId, { texto: texto.trim(), categoria })
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
    <section className={estilos.secao} aria-labelledby="memorias-titulo">
      <div className={estilos.secaoTopo}>
        <h2 className={estilos.secaoTitulo} id="memorias-titulo">
          O que a Sera sabe sobre você
        </h2>
        {!carregando && memorias.length > 0 ? (
          <span className={estilos.chip}>{memorias.length}/100</span>
        ) : null}
      </div>
      <p className={estilos.secaoTexto}>
        Fatos que ela guardou para lembrar nas próximas conversas. Você pode corrigir ou
        apagar quando quiser.
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

      {!carregando && !erro && memorias.length === 0 ? (
        <p className={estilos.vazio}>
          Ainda não guardei nada sobre você. Na conversa, peça “lembre disso” ou conte
          algo que valha a pena lembrar.
        </p>
      ) : null}

      <ul className={estilos.lista}>
        {memorias.map((memoria) => (
          <li className={estilos.item} key={memoria.id}>
            {editandoId === memoria.id ? (
              <form className={estilos.formulario} onSubmit={salvar}>
                <label
                  className={estilos.campoRotulo}
                  htmlFor={`memoria-texto-${memoria.id}`}
                >
                  Fato
                </label>
                <textarea
                  id={`memoria-texto-${memoria.id}`}
                  className={estilos.textarea}
                  value={texto}
                  onChange={(evento) => setTexto(evento.target.value)}
                  maxLength={300}
                  rows={2}
                />
                <label
                  className={estilos.campoRotulo}
                  htmlFor={`memoria-categoria-${memoria.id}`}
                >
                  Categoria
                </label>
                <select
                  id={`memoria-categoria-${memoria.id}`}
                  className={estilos.select}
                  value={categoria}
                  onChange={(evento) =>
                    setCategoria(evento.target.value as CategoriaMemoria)
                  }
                >
                  {CATEGORIAS.map((chave) => (
                    <option key={chave} value={chave}>
                      {ROTULO_CATEGORIA[chave]}
                    </option>
                  ))}
                </select>
                <div className={estilos.acoesInline}>
                  <Botao
                    type="submit"
                    className={estilos.botaoPequeno}
                    carregando={salvando}
                    disabled={!texto.trim()}
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
                  <p className={estilos.itemTexto}>{memoria.texto}</p>
                  <span className={estilos.chip}>
                    {ROTULO_CATEGORIA[memoria.categoria]}
                  </span>
                </div>
                <div className={estilos.itemAcoes}>
                  <Botao
                    variante="fantasma"
                    className={estilos.botaoPequeno}
                    aria-label={`Editar memória: ${memoria.texto}`}
                    onClick={() => comecarEdicao(memoria)}
                  >
                    Editar
                  </Botao>
                  <Botao
                    variante="fantasma"
                    className={estilos.botaoPequeno}
                    aria-label={`Apagar memória: ${memoria.texto}`}
                    onClick={() => {
                      setConfirmandoId(memoria.id)
                      setErroLocal(null)
                    }}
                  >
                    Apagar
                  </Botao>
                </div>
              </>
            )}

            {confirmandoId === memoria.id ? (
              <div className={estilos.confirmacao} role="alert">
                <p className={estilos.confirmacaoTexto}>
                  Apagar esta memória? A Sera não vai mais lembrar disso.
                </p>
                <div className={estilos.acoesInline}>
                  <Botao
                    variante="perigo"
                    className={estilos.botaoPequeno}
                    carregando={apagandoId === memoria.id}
                    onClick={() => void apagar(memoria.id)}
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
        ))}
      </ul>
    </section>
  )
}
