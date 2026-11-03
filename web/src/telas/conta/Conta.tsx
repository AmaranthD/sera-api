import { useCallback, useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { ehSessaoExpirada, mensagemDoErro } from '../../api/erros'
import { useSessao } from '../../auth/contexto'
import { usePessoa } from '../../pessoa/contexto'
import {
  DESCRICAO_PERFIL,
  ROTULO_FAIXA,
  ROTULO_PERFIL,
  iniciais,
} from '../../dominios/texto'
import type {
  Ajuste,
  AtualizacaoAjuste,
  AtualizacaoMemoria,
  Memoria,
} from '../../dominios/tipos'
import { Banner } from '../../componentes/Banner'
import { Botao } from '../../componentes/Botao'
import { BotaoInstalar } from '../../componentes/BotaoInstalar'
import { Icone } from '../../componentes/Icone'
import { Marca } from '../../componentes/Marca'
import { SecaoAjustes } from './Ajustes'
import { SecaoMemorias } from './Memorias'
import { SecaoMicrofone } from './Microfone'
import estilos from './Conta.module.css'

type Saude = 'verificando' | 'ok' | 'falha'

export function Conta() {
  const { sessao, api, sair } = useSessao()
  const { pessoa, carregando } = usePessoa()
  const [saude, setSaude] = useState<Saude>('verificando')
  const [saindo, setSaindo] = useState(false)
  const [memorias, setMemorias] = useState<Memoria[]>([])
  const [ajustes, setAjustes] = useState<Ajuste[]>([])
  const [carregandoDados, setCarregandoDados] = useState(true)
  const [erroDados, setErroDados] = useState<string | null>(null)
  const [baixando, setBaixando] = useState(false)
  const [erroExportacao, setErroExportacao] = useState<string | null>(null)

  useEffect(() => {
    let ativo = true
    api
      .saude()
      .then(() => {
        if (ativo) setSaude('ok')
      })
      .catch(() => {
        if (ativo) setSaude('falha')
      })
    return () => {
      ativo = false
    }
  }, [api])

  const carregarDados = useCallback(async () => {
    if (!pessoa) return
    setCarregandoDados(true)
    setErroDados(null)
    try {
      const [listaMemorias, listaAjustes] = await Promise.all([
        api.listarMemorias(pessoa.id),
        api.listarAjustes(pessoa.id),
      ])
      setMemorias(listaMemorias)
      setAjustes(listaAjustes)
    } catch (falha) {
      if (ehSessaoExpirada(falha)) {
        await sair()
        return
      }
      setErroDados(mensagemDoErro(falha))
    } finally {
      setCarregandoDados(false)
    }
  }, [api, pessoa, sair])

  useEffect(() => {
    void carregarDados()
  }, [carregarDados])

  const atualizarMemoria = useCallback(
    async (id: string, dados: AtualizacaoMemoria) => {
      if (!pessoa) return
      const atualizada = await api.atualizarMemoria(pessoa.id, id, dados)
      setMemorias((atuais) =>
        atuais.map((memoria) => (memoria.id === id ? atualizada : memoria)),
      )
    },
    [api, pessoa],
  )

  const apagarMemoria = useCallback(
    async (id: string) => {
      if (!pessoa) return
      await api.apagarMemoria(pessoa.id, id)
      setMemorias((atuais) => atuais.filter((memoria) => memoria.id !== id))
    },
    [api, pessoa],
  )

  const atualizarAjuste = useCallback(
    async (id: string, dados: AtualizacaoAjuste) => {
      if (!pessoa) return
      const atualizado = await api.atualizarAjuste(pessoa.id, id, dados)
      setAjustes((atuais) =>
        atuais.map((ajuste) => (ajuste.id === id ? atualizado : ajuste)),
      )
    },
    [api, pessoa],
  )

  const apagarAjuste = useCallback(
    async (id: string) => {
      if (!pessoa) return
      await api.apagarAjuste(pessoa.id, id)
      setAjustes((atuais) => atuais.filter((ajuste) => ajuste.id !== id))
    },
    [api, pessoa],
  )

  async function baixarDados() {
    if (!pessoa) return
    setBaixando(true)
    setErroExportacao(null)
    try {
      const dados = await api.exportarDados(pessoa.id)
      const blob = new Blob([JSON.stringify(dados, null, 2)], {
        type: 'application/json',
      })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'sera-dados.json'
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch (falha) {
      if (ehSessaoExpirada(falha)) {
        await sair()
        return
      }
      setErroExportacao(mensagemDoErro(falha))
    } finally {
      setBaixando(false)
    }
  }

  if (carregando) return null
  if (!pessoa) return <Navigate to="/onboarding" replace />

  const email = sessao?.user.email ?? '—'

  return (
    <div className={estilos.pagina}>
      <header className={estilos.topo}>
        <Marca pequena legenda="conta" />
        <Link to="/" className={estilos.voltar}>
          <Icone nome="voltar" tamanho={17} />
          Voltar para a conversa
        </Link>
      </header>

      <main className={estilos.cartao} id="conteudo">
        <section className={estilos.perfil}>
          <span className={estilos.avatar} aria-hidden="true">
            {iniciais(pessoa.nome)}
          </span>
          <div className={estilos.perfilTexto}>
            <h1 className={estilos.nome}>{pessoa.nome}</h1>
            <p className={estilos.resumo}>
              {ROTULO_FAIXA[pessoa.faixa_etaria]} · {ROTULO_PERFIL[pessoa.perfil]}
            </p>
          </div>
        </section>

        <section className={estilos.secao}>
          <h2 className={estilos.secaoTitulo}>Seu perfil</h2>
          <p className={estilos.secaoTexto}>
            É assim que a Sera ajusta o jeito de conversar com você.
          </p>
          <div className={estilos.linha}>
            <span className={estilos.rotulo}>Nome</span>
            <span className={estilos.valor}>{pessoa.nome}</span>
          </div>
          <div className={estilos.linha}>
            <span className={estilos.rotulo}>Faixa etária</span>
            <span className={estilos.valor}>{ROTULO_FAIXA[pessoa.faixa_etaria]}</span>
          </div>
          <div className={estilos.linha}>
            <span className={estilos.rotulo}>Jeito de conversar</span>
            <span className={estilos.valor}>{ROTULO_PERFIL[pessoa.perfil]}</span>
          </div>
          <p className={`${estilos.secaoTexto} ${estilos.secaoTextoFinal}`}>
            {DESCRICAO_PERFIL[pessoa.perfil]}
          </p>
        </section>

        <SecaoMemorias
          memorias={memorias}
          carregando={carregandoDados}
          erro={erroDados}
          aoAtualizar={atualizarMemoria}
          aoApagar={apagarMemoria}
          aoTentarDeNovo={() => void carregarDados()}
        />

        <SecaoAjustes
          ajustes={ajustes}
          carregando={carregandoDados}
          erro={erroDados}
          aoAtualizar={atualizarAjuste}
          aoApagar={apagarAjuste}
          aoTentarDeNovo={() => void carregarDados()}
        />

        <SecaoMicrofone />

        <section className={estilos.secao} aria-labelledby="dados-titulo">
          <h2 className={estilos.secaoTitulo} id="dados-titulo">
            Seus dados
          </h2>
          <p className={estilos.secaoTexto}>
            Baixe uma cópia do seu perfil, do que a Sera aprendeu e das suas conversas
            em um arquivo JSON.
          </p>
          {erroExportacao ? <Banner tipo="erro">{erroExportacao}</Banner> : null}
          <Botao
            variante="secundario"
            carregando={baixando}
            icone={<Icone nome="instalar" tamanho={17} />}
            onClick={() => void baixarDados()}
          >
            Baixar meus dados (JSON)
          </Botao>
        </section>

        <section className={estilos.secao} aria-labelledby="app-titulo">
          <h2 className={estilos.secaoTitulo} id="app-titulo">
            Aplicativo
          </h2>
          <p className={estilos.secaoTexto}>
            Instale na tela inicial para abrir como um app ou envie o link de instalação
            para alguém.
          </p>
          <BotaoInstalar larguraTotal />
          <Link to="/instalar" className={estilos.linkInstalar}>
            Abrir página de instalação e compartilhamento
          </Link>
        </section>

        <section className={estilos.secao}>
          <h2 className={estilos.secaoTitulo}>Sessão</h2>
          <div className={estilos.linha}>
            <span className={estilos.rotulo}>E-mail</span>
            <span className={estilos.valor}>{email}</span>
          </div>
          <div className={estilos.linha}>
            <span className={estilos.rotulo}>Conexão com a Sera</span>
            <span className={estilos.estado}>
              <span
                className={
                  saude === 'ok'
                    ? estilos.pontoOk
                    : saude === 'falha'
                      ? estilos.pontoFalha
                      : estilos.pontoEspera
                }
                aria-hidden="true"
              />
              {saude === 'ok'
                ? 'Funcionando'
                : saude === 'falha'
                  ? 'Indisponível agora'
                  : 'Verificando…'}
            </span>
          </div>
          <div className={estilos.acoes}>
            <Botao
              variante="perigo"
              carregando={saindo}
              icone={<Icone nome="sair" tamanho={17} />}
              onClick={() => {
                setSaindo(true)
                void sair().finally(() => setSaindo(false))
              }}
            >
              Sair da conta
            </Botao>
          </div>
          <p className={estilos.nota}>
            A Sera é uma IA e não substitui ajuda humana. Em emergências, ligue 192
            (SAMU) ou 188 (CVV). Suas conversas são visíveis apenas para você.
          </p>
        </section>
      </main>
    </div>
  )
}
