import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import type { ApiSera } from '../../api/sera'
import { mensagemDoErro } from '../../api/erros'
import type { ConteudoJW } from '../../dominios/tipos'
import { JanelaJWContext } from './janelaJWContexto'
import estilos from './JanelaJW.module.css'

interface ProviderProps {
  api: ApiSera
  children: ReactNode
}

export function JanelaJWProvider({ api, children }: ProviderProps) {
  const [janela, setJanela] = useState<{
    url: string
    referencia?: string
  } | null>(null)
  const abrir = useCallback((destino: string, texto?: string) => {
    if (destino) setJanela({ url: destino, referencia: texto })
  }, [])

  return (
    <JanelaJWContext.Provider value={abrir}>
      {children}
      <ConteudoJWModal
        api={api}
        url={janela?.url ?? null}
        referencia={janela?.referencia}
        aoFechar={() => setJanela(null)}
      />
    </JanelaJWContext.Provider>
  )
}

interface ModalProps {
  api: ApiSera
  url: string | null
  referencia?: string
  aoFechar: () => void
}

function ConteudoJWModal({ api, url, referencia, aoFechar }: ModalProps) {
  const dialogoRef = useRef<HTMLDialogElement>(null)
  const tituloId = useId()
  const [conteudo, setConteudo] = useState<ConteudoJW | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    const dialogo = dialogoRef.current
    if (!url || !dialogo) return
    if (!dialogo.open) dialogo.showModal()
    return () => {
      if (dialogo.open) dialogo.close()
    }
  }, [url])

  useEffect(() => {
    if (!url) return
    let ativo = true
    setCarregando(true)
    setErro(null)
    setConteudo(null)
    api
      .conteudoJW(url, referencia)
      .then((resposta) => {
        if (ativo) setConteudo(resposta)
      })
      .catch((falha) => {
        if (ativo) setErro(mensagemDoErro(falha))
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })
    return () => {
      ativo = false
    }
  }, [api, url, referencia])

  if (!url) return null

  return (
    <dialog
      ref={dialogoRef}
      className={estilos.dialogo}
      aria-labelledby={tituloId}
      onCancel={(evento) => {
        evento.preventDefault()
        aoFechar()
      }}
      onClose={aoFechar}
      onClick={(evento) => {
        if (evento.target === dialogoRef.current) aoFechar()
      }}
    >
      <article className={estilos.cartao}>
        <header className={estilos.topo}>
          <div className={estilos.tituloBloco}>
            <span className={estilos.sobrescrito}>JW.org</span>
            <h2 className={estilos.titulo} id={tituloId}>
              {conteudo?.titulo ?? 'Conteúdo'}
            </h2>
          </div>
          <button
            type="button"
            className={estilos.fechar}
            onClick={aoFechar}
            aria-label="Fechar janela"
            title="Fechar"
          >
            ×
          </button>
        </header>

        <div className={estilos.corpo}>
          {carregando ? (
            <p className={estilos.aviso}>Buscando no JW.org…</p>
          ) : erro ? (
            <p className={`${estilos.aviso} ${estilos.erro}`} role="alert">
              {erro}
            </p>
          ) : conteudo ? (
            conteudo.paragrafos.map((paragrafo, indice) => (
              <p className={estilos.paragrafo} key={indice}>
                {paragrafo}
              </p>
            ))
          ) : null}
        </div>

        <footer className={estilos.rodape}>
          <a
            className={estilos.externo}
            href={url}
            target="_blank"
            rel="noopener noreferrer"
          >
            Abrir no JW.org
          </a>
          <button type="button" className={estilos.fecharRodape} onClick={aoFechar}>
            Fechar
          </button>
        </footer>
      </article>
    </dialog>
  )
}
