import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Botao } from '../../componentes/Botao'
import { Icone } from '../../componentes/Icone'
import { Marca } from '../../componentes/Marca'
import { useInstalacao } from '../../pwa/usePwa'
import estilos from './Instalar.module.css'

function linkDeInstalacao(): string {
  return `${window.location.origin}/instalar`
}

export function Instalar() {
  const { podeInstalar, instalado, ehIOS, instalar } = useInstalacao()
  const navegar = useNavigate()
  const [copiado, setCopiado] = useState(false)
  const [baixando, setBaixando] = useState(false)

  const link = linkDeInstalacao()

  async function copiar() {
    try {
      await navigator.clipboard.writeText(link)
      setCopiado(true)
      window.setTimeout(() => setCopiado(false), 2500)
    } catch {
      window.prompt('Copie o link de instalação:', link)
    }
  }

  function compartilhar() {
    const texto = `Instale a Sera no celular: ${link}`
    window.open(
      `https://wa.me/?text=${encodeURIComponent(texto)}`,
      '_blank',
      'noopener,noreferrer',
    )
  }

  async function instalarAgora() {
    setBaixando(true)
    try {
      await instalar()
    } finally {
      setBaixando(false)
    }
  }

  return (
    <div className={estilos.pagina}>
      <div className={estilos.fundo} aria-hidden="true" />
      <div className={estilos.veu} aria-hidden="true" />

      <main className={estilos.cartao} id="conteudo">
        <div className={estilos.topo}>
          <Marca clara legenda="instalar" />
          <span className={estilos.selo}>
            <Icone nome="escudo" tamanho={15} />
            PWA
          </span>
        </div>

        <p className={estilos.olho}>LEVE A SERA COM VOCÊ</p>
        <h1 className={estilos.titulo}>Um atalho no celular, como um app.</h1>
        <p className={estilos.texto}>
          A Sera abre em tela cheia, sem barra de navegador e sem precisar procurar o
          site toda vez. O mesmo login, as mesmas conversas.
        </p>

        {instalado ? (
          <div className={estilos.aviso}>A Sera já está instalada neste aparelho.</div>
        ) : null}

        <div className={estilos.acoes}>
          {instalado ? (
            <Botao
              larguraTotal
              icone={<Icone nome="enviar" tamanho={17} />}
              onClick={() => navegar('/')}
            >
              Abrir a Sera
            </Botao>
          ) : podeInstalar ? (
            <Botao
              larguraTotal
              carregando={baixando}
              icone={<Icone nome="instalar" tamanho={17} />}
              onClick={() => void instalarAgora()}
            >
              Instalar agora
            </Botao>
          ) : (
            <div className={estilos.passos}>
              <strong>{ehIOS ? 'No iPhone:' : 'No Android:'}</strong>{' '}
              {ehIOS
                ? 'abra no Safari, toque em Compartilhar e depois em “Adicionar à Tela de Início”.'
                : 'abra no Chrome, toque no menu ⋮ e escolha “Instalar app” ou “Adicionar à tela inicial”.'}
            </div>
          )}
        </div>

        <div className={estilos.acoesSecundarias}>
          <Botao
            variante="claro"
            icone={<Icone nome="check" tamanho={16} />}
            onClick={() => void copiar()}
          >
            {copiado ? 'Link copiado' : 'Copiar link'}
          </Botao>
          <Botao
            variante="claro"
            icone={<Icone nome="enviar" tamanho={16} />}
            onClick={compartilhar}
          >
            Enviar no WhatsApp
          </Botao>
        </div>

        <p className={estilos.nota}>
          Se o ícone ainda estiver antigo ou a barra do sistema estiver com outra cor,
          remova o atalho, limpe os dados do site e instale de novo. A cor da barra de
          navegação do Android segue o tema do aparelho; o app usa azul-noite e ouro.
        </p>

        <Link to="/login" className={estilos.voltar}>
          Voltar para entrar
        </Link>
      </main>
    </div>
  )
}
