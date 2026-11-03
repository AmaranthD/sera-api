import { mensagemDeErroVoz } from './ouvir'

export type EstadoPermissao =
  | 'granted'
  | 'denied'
  | 'prompt'
  | 'desconhecido'

export async function consultarPermissaoMicrofone(): Promise<EstadoPermissao> {
  if (
    typeof navigator === 'undefined' ||
    !navigator.permissions?.query
  ) {
    return 'desconhecido'
  }
  try {
    const status = await navigator.permissions.query({
      name: 'microphone' as PermissionName,
    })
    return status.state as EstadoPermissao
  } catch {
    return 'desconhecido'
  }
}

export async function pedirPermissaoMicrofone(): Promise<{
  ok: boolean
  erro?: string
}> {
  if (!window.isSecureContext) {
    return { ok: false, erro: 'O microfone exige uma conexão segura (HTTPS).' }
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    return {
      ok: false,
      erro: 'Este navegador não oferece acesso direto ao microfone.',
    }
  }
  try {
    const fluxo = await navigator.mediaDevices.getUserMedia({ audio: true })
    for (const faixa of fluxo.getTracks()) faixa.stop()
    return { ok: true }
  } catch (erro) {
    const nome = erro instanceof DOMException ? erro.name : 'audio-capture'
    return { ok: false, erro: mensagemDeErroVoz(nome) }
  }
}
