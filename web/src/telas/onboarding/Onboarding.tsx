import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useSessao } from '../../auth/contexto'
import { usePessoa } from '../../pessoa/contexto'
import { DESCRICAO_PERFIL, ROTULO_PERFIL } from '../../dominios/texto'
import type { FaixaEtaria, Perfil } from '../../dominios/tipos'
import { Banner } from '../../componentes/Banner'
import { Botao } from '../../componentes/Botao'
import { Campo } from '../../componentes/Campo'
import { CarregandoTela } from '../../componentes/Carregando'
import { Icone } from '../../componentes/Icone'
import { Marca } from '../../componentes/Marca'
import estilos from './Onboarding.module.css'

const FAIXAS: Array<{ valor: FaixaEtaria; titulo: string; texto: string }> = [
  { valor: 'adulto', titulo: 'Adulto', texto: '18 anos ou mais' },
  { valor: 'adolescente', titulo: 'Adolescente', texto: 'De 13 a 17 anos' },
  { valor: 'crianca', titulo: 'Criança', texto: 'Até 12 anos' },
]

const PERFIS: Perfil[] = ['padrao', 'crianca_adolescente', 'idoso_ou_pouco_tecnico']

export function Onboarding() {
  const { sessao, carregando, sair } = useSessao()
  const { pessoa, carregando: carregandoPessoa, criarPessoa } = usePessoa()
  const navegar = useNavigate()

  const [nome, setNome] = useState('')
  const [faixa, setFaixa] = useState<FaixaEtaria | ''>('')
  const [perfil, setPerfil] = useState<Perfil>('padrao')
  const [perfilManual, setPerfilManual] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [salvando, setSalvando] = useState(false)

  if (carregando || carregandoPessoa) return <CarregandoTela />
  if (!sessao) return <Navigate to="/login" replace />
  if (pessoa) return <Navigate to="/" replace />

  const escolherFaixa = (valor: FaixaEtaria) => {
    setFaixa(valor)
    if (!perfilManual) {
      setPerfil(
        valor === 'crianca' || valor === 'adolescente'
          ? 'crianca_adolescente'
          : 'padrao',
      )
    }
  }

  const enviar = async (evento: React.FormEvent) => {
    evento.preventDefault()
    const limpo = nome.trim()
    if (!limpo) {
      setErro('Como a Sera pode te chamar?')
      return
    }
    if (limpo.length > 80) {
      setErro('Use um nome com até 80 caracteres.')
      return
    }
    if (!faixa) {
      setErro('Escolha sua faixa etária para continuar.')
      return
    }
    setSalvando(true)
    setErro(null)
    try {
      await criarPessoa({
        nome: limpo,
        faixa_etaria: faixa,
        perfil,
      })
      navegar('/', { replace: true })
    } catch (falha) {
      setErro(
        falha instanceof Error ? falha.message : 'Não foi possível salvar seu perfil.',
      )
    } finally {
      setSalvando(false)
    }
  }

  return (
    <div className={estilos.pagina}>
      <header className={estilos.topo}>
        <Marca pequena legenda="primeiro acesso" />
        <button type="button" className={estilos.voltar} onClick={() => void sair()}>
          <Icone nome="sair" tamanho={17} />
          Sair
        </button>
      </header>

      <main className={estilos.cartao} id="conteudo">
        <p className={estilos.passos}>Antes de começar</p>
        <h1 className={estilos.titulo}>Como a Sera pode te chamar?</h1>
        <p className={estilos.subtitulo}>
          Isso ajuda a Sera a falar do seu jeito. Só você vê suas conversas e suas
          informações.
        </p>

        <form className={estilos.formulario} onSubmit={enviar} noValidate>
          {erro ? <Banner tipo="erro">{erro}</Banner> : null}

          <Campo
            rotulo="Seu nome"
            autoComplete="given-name"
            placeholder="Como você prefere ser chamado"
            maxLength={80}
            value={nome}
            onChange={(evento) => setNome(evento.target.value)}
            dica="Pode ser só o primeiro nome."
            required
          />

          <fieldset className={estilos.grupo}>
            <legend className={estilos.legenda}>Sua faixa etária</legend>
            <p className={estilos.ajuda}>
              A Sera ajusta o humor e o cuidado conforme a idade.
            </p>
            <div className={`${estilos.opcoes} ${estilos.opcoesTres}`}>
              {FAIXAS.map((item) => (
                <label key={item.valor} className={estilos.opcao}>
                  <input
                    type="radio"
                    name="faixa"
                    value={item.valor}
                    checked={faixa === item.valor}
                    onChange={() => escolherFaixa(item.valor)}
                  />
                  <span className={estilos.marcaSelecionada} aria-hidden="true">
                    <Icone nome="check" tamanho={16} />
                  </span>
                  <span className={estilos.opcaoTitulo}>{item.titulo}</span>
                  <span className={estilos.opcaoTexto}>{item.texto}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset className={estilos.grupo}>
            <legend className={estilos.legenda}>Jeito de conversar</legend>
            <p className={estilos.ajuda}>
              Você pode escolher o que combina mais com você agora.
            </p>
            <div className={estilos.opcoes}>
              {PERFIS.map((item) => (
                <label key={item} className={estilos.opcao}>
                  <input
                    type="radio"
                    name="perfil"
                    value={item}
                    checked={perfil === item}
                    onChange={() => {
                      setPerfil(item)
                      setPerfilManual(true)
                    }}
                  />
                  <span className={estilos.marcaSelecionada} aria-hidden="true">
                    <Icone nome="check" tamanho={16} />
                  </span>
                  <span className={estilos.opcaoTitulo}>{ROTULO_PERFIL[item]}</span>
                  <span className={estilos.opcaoTexto}>{DESCRICAO_PERFIL[item]}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <div className={estilos.acoes}>
            <p className={estilos.nota}>
              A Sera é uma IA. Não substitui ajuda humana quando você precisa.
            </p>
            <Botao type="submit" carregando={salvando}>
              Começar a conversar
            </Botao>
          </div>
        </form>
      </main>
    </div>
  )
}
