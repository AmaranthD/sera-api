interface Props {
  className?: string
}

export function IlustracaoVazia({ className }: Props) {
  return (
    <svg
      className={className}
      viewBox="0 0 40 40"
      width="112"
      height="112"
      shapeRendering="crispEdges"
      role="presentation"
      aria-hidden="true"
      focusable="false"
    >
      <rect x="10" y="4" width="20" height="3" fill="var(--indigo-escuro)" />
      <rect x="12" y="7" width="16" height="2" fill="var(--indigo)" opacity="0.55" />

      <rect x="13" y="9" width="2" height="7" fill="var(--indigo)" opacity="0.55" />
      <rect x="25" y="9" width="2" height="7" fill="var(--indigo)" opacity="0.55" />
      <rect x="15" y="9" width="10" height="2" fill="var(--ouro-claro)" />
      <rect x="17" y="11" width="6" height="2" fill="var(--ouro-claro)" />
      <rect x="19" y="13" width="2" height="2" fill="var(--ouro-claro)" />
      <rect x="18" y="15" width="4" height="1" fill="var(--ouro)" />
      <rect x="19" y="16" width="2" height="2" fill="var(--ouro)" />
      <rect x="17" y="18" width="6" height="1" fill="var(--ouro)" />
      <rect x="15" y="19" width="10" height="2" fill="var(--ouro-claro)" />

      <rect x="13" y="24" width="2" height="7" fill="var(--indigo)" opacity="0.55" />
      <rect x="25" y="24" width="2" height="7" fill="var(--indigo)" opacity="0.55" />
      <rect x="15" y="25" width="10" height="2" fill="var(--ouro-claro)" />
      <rect x="17" y="27" width="6" height="2" fill="var(--ouro-claro)" />
      <rect x="19" y="29" width="2" height="2" fill="var(--ouro)" />
      <rect x="12" y="31" width="16" height="2" fill="var(--indigo)" opacity="0.55" />
      <rect x="10" y="33" width="20" height="3" fill="var(--indigo-escuro)" />

      <rect x="7" y="12" width="2" height="2" fill="var(--ouro)" />
      <rect x="31" y="22" width="2" height="2" fill="var(--ouro)" />
      <rect x="28" y="8" width="1" height="1" fill="var(--ouro)" />
      <rect x="9" y="26" width="1" height="1" fill="var(--ouro)" />
    </svg>
  )
}
