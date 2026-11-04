import { useMemo } from 'react'
import Markdown, { type Components } from 'react-markdown'
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize'
import remarkBreaks from 'remark-breaks'
import remarkGfm from 'remark-gfm'
import { useJanelaJW } from './janelaJWContexto'
import estilos from './MensagemMarkdown.module.css'

const esquema = {
  ...defaultSchema,
  tagNames: (defaultSchema.tagNames ?? []).filter((tag) => tag !== 'img'),
}

function ehLinkJW(href: string | undefined): boolean {
  if (!href) return false
  try {
    const url = new URL(href)
    if (url.hash === '#externo') return false
    return (
      (url.protocol === 'https:' || url.protocol === 'http:') &&
      (url.hostname === 'jw.org' || url.hostname.endsWith('.jw.org'))
    )
  } catch {
    return false
  }
}

export function MensagemMarkdown({ texto }: { texto: string }) {
  const abrirJanela = useJanelaJW()

  const componentes = useMemo<Components>(
    () => ({
      a({ href, children, title }) {
        const externo = typeof href === 'string' && /^https?:\/\//i.test(href)
        if (typeof href === 'string' && ehLinkJW(href) && abrirJanela) {
          return (
            <a
              href={href}
              title={title}
              className={estilos.linkJw}
              onClick={(evento) => {
                evento.preventDefault()
                const texto =
                  evento.currentTarget.textContent?.trim().slice(0, 120) ?? ''
                abrirJanela(href, texto)
              }}
            >
              {children}
            </a>
          )
        }
        return (
          <a
            href={href}
            title={title}
            {...(externo
              ? { target: '_blank', rel: 'noopener noreferrer nofollow' }
              : {})}
          >
            {children}
          </a>
        )
      },
      table({ children }) {
        return (
          <div className={estilos.tabela}>
            <table>{children}</table>
          </div>
        )
      },
    }),
    [abrirJanela],
  )

  return (
    <div className={estilos.markdown}>
      <Markdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        rehypePlugins={[[rehypeSanitize, esquema]]}
        components={componentes}
        skipHtml
      >
        {texto}
      </Markdown>
    </div>
  )
}
