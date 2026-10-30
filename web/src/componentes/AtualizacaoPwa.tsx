import { useRegisterSW } from 'virtual:pwa-register/react'
import { Icone } from './Icone'
import estilos from './AtualizacaoPwa.module.css'

export function AtualizacaoPwa() {
  const {
    offlineReady: [prontoOffline, setProntoOffline],
    needRefresh: [precisaAtualizar, setPrecisaAtualizar],
    updateServiceWorker,
  } = useRegisterSW()

  if (!prontoOffline && !precisaAtualizar) return null

  return (
    <div className={estilos.banner} role="status">
      <span className={estilos.texto}>
        {precisaAtualizar
          ? 'Uma nova versão da Sera está pronta.'
          : 'A Sera já pode abrir sem internet.'}
      </span>
      <div className={estilos.acoes}>
        {precisaAtualizar ? (
          <button
            type="button"
            className={estilos.atualizar}
            onClick={() => void updateServiceWorker(true)}
          >
            Atualizar
          </button>
        ) : null}
        <button
          type="button"
          className={estilos.fechar}
          aria-label="Fechar aviso"
          onClick={() => {
            setProntoOffline(false)
            setPrecisaAtualizar(false)
          }}
        >
          <Icone nome="fechar" tamanho={18} />
        </button>
      </div>
    </div>
  )
}
