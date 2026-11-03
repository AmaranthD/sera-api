import type { ApiSera } from '../api/sera'
import { falar, falarNeural, FalaCancelada } from './falar'

/** Usa a voz neural quando disponível/ligada; cai para a voz do aparelho. */
export async function falarResposta(
  api: ApiSera,
  texto: string,
  id: string,
  neural: boolean,
): Promise<void> {
  if (neural) {
    try {
      const tocou = await falarNeural(() => api.gerarAudio(texto), { id })
      if (tocou) return
    } catch (erro) {
      if (erro instanceof FalaCancelada) return
    }
  }
  falar(texto, { id })
}
