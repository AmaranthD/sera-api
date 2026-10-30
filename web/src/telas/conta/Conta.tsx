import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useSessao } from '../../auth/contexto'
import { usePessoa } from '../../pessoa/contexto'
import {
  DESCRICAO_PERFIL,
  ROTULO_FAIXA,
  ROTULO_PERFIL,
  iniciais,
} from '../../dominios/texto'
import { Botao } from '../../componentes/Botao'
import { BotaoInstalar } from '../../componentes/BotaoInstalar'
import { Icone } from '../../componentes/Icone'
import { Marca } from '../../componentes/Marca'
import { useInstalacao } from '../../pwa/usePwa'
import estilos from './Conta.module.css'

type Saude = 'verificando' | 'ok' | 'falha'

export function Conta() {
  const { sessao, api, sair } = useSessao()
  const { pessoa, carregando } = usePessoa()
  const { podeInstalar, instalado, ehIOS } = useInstalacao()
  const [saude, setSaude] = useState<Saude>('verificando')
  const [saindo, setSaindo] = useState(false)

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

        {!instalado && (podeInstalar || ehIOS) ? (
          <section className={estilos.secao}>
            <h2 className={estilos.secaoTitulo}>Aplicativo</h2>
            <p className={estilos.secaoTexto}>
              Instale a Sera na tela inicial para abrir como um app, sem passar pelo
              navegador.
            </p>
            <BotaoInstalar larguraTotal />
          </section>
        ) : null}

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
