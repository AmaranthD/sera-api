import type { ApiSera } from './sera'

const INTERVALO_MS = 5 * 60 * 1000

let ultimaTentativa = 0
let emAndamento: Promise<void> | null = null

/**
 * Aquece a API no máximo a cada 5 minutos. Chamadas concorrentes reaproveitam
 * a mesma requisição, para não abrir vários cold starts ao mesmo tempo.
 */
export function aquecerApi(api: ApiSera): Promise<void> {
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    return Promise.resolve()
  }
  if (emAndamento) return emAndamento

  const agora = Date.now()
  if (agora - ultimaTentativa < INTERVALO_MS) return Promise.resolve()
  ultimaTentativa = agora

  emAndamento = api.aquecer().finally(() => {
    emAndamento = null
  })
  return emAndamento
}
