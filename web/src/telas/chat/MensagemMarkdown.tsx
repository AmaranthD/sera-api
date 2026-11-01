import Markdown, { type Components } from 'react-markdown'
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize'
import remarkBreaks from 'remark-breaks'
import remarkGfm from 'remark-gfm'
import estilos from './MensagemMarkdown.module.css'

const esquema = {
  ...defaultSchema,
  tagNames: (defaultSchema.tagNames ?? []).filter((tag) => tag !== 'img'),
}

const componentes: Components = {
  a({ href, children, title }) {
    const externo = typeof href === 'string' && /^https?:\/\//i.test(href)
    return (
      <a
        href={href}
        title={title}
        {...(externo ? { target: '_blank', rel: 'noopener noreferrer nofollow' } : {})}
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
}

export function MensagemMarkdown({ texto }: { texto: string }) {
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
