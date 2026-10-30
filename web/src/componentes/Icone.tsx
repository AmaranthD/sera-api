import type { SVGProps } from 'react'

export type NomeIcone =
  | 'mais'
  | 'menu'
  | 'enviar'
  | 'parar'
  | 'sair'
  | 'conta'
  | 'instalar'
  | 'check'
  | 'voltar'
  | 'fechar'
  | 'alerta'
  | 'offline'
  | 'atualizar'
  | 'escudo'
  | 'relogio'

const CAMINHOS: Record<NomeIcone, React.ReactNode> = {
  mais: <path d="M12 5v14M5 12h14" />,
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  enviar: <path d="M21.5 2.5 11 13M21.5 2.5l-6.8 19-3.7-8.5-8.5-3.7 19-6.8Z" />,
  parar: <rect x="7" y="7" width="10" height="10" rx="2" />,
  sair: (
    <>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <path d="m16 17 5-5-5-5M21 12H9" />
    </>
  ),
  conta: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0 1 16 0" />
    </>
  ),
  instalar: (
    <>
      <path d="M12 3v12m0 0 4-4m-4 4-4-4" />
      <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
    </>
  ),
  check: <path d="m20 6-11 11-5-5" />,
  voltar: <path d="M19 12H5m0 0 7 7m-7-7 7-7" />,
  fechar: <path d="M18 6 6 18M6 6l12 12" />,
  alerta: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v5M12 16.5v.01" />
    </>
  ),
  offline: (
    <>
      <path d="M2 2l20 20" />
      <path d="M8.5 8.5a9 9 0 0 1 2.6-.8M5 12.5a14 14 0 0 1 4-2.2M2 8.8A19 19 0 0 1 8.7 6M15.5 8.5a9 9 0 0 1 5.2 2.6M18.6 12.4a14 14 0 0 0-2.3-1.6M22 8.8a19 19 0 0 0-4.2-2.3M12 20h.01" />
    </>
  ),
  atualizar: (
    <>
      <path d="M21 12a9 9 0 1 1-2.6-6.4" />
      <path d="M21 3v6h-6" />
    </>
  ),
  escudo: <path d="M12 3 5 6v6c0 4.4 3 7.4 7 9 4-1.6 7-4.6 7-9V6l-7-3Z" />,
  relogio: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
}

interface Props extends SVGProps<SVGSVGElement> {
  nome: NomeIcone
  tamanho?: number
}

export function Icone({ nome, tamanho = 20, ...resto }: Props) {
  return (
    <svg
      width={tamanho}
      height={tamanho}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...resto}
    >
      {CAMINHOS[nome]}
    </svg>
  )
}
