import type { ApiSera } from '../api/sera'

export type EstadoPush = 'nao_suportado' | 'negado' | 'ativo' | 'inativo'

export function pushSuportado(): boolean {
  return (
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  )
}

function chaveParaBytes(base64: string): Uint8Array<ArrayBuffer> {
  const preenchido = (base64 + '='.repeat((4 - (base64.length % 4)) % 4))
    .replace(/-/g, '+')
    .replace(/_/g, '/')
  const bruto = window.atob(preenchido)
  const bytes = new Uint8Array(bruto.length)
  for (let indice = 0; indice < bruto.length; indice += 1) {
    bytes[indice] = bruto.charCodeAt(indice)
  }
  return bytes
}

async function registroPush(): Promise<ServiceWorkerRegistration | null> {
  return (await navigator.serviceWorker.getRegistration()) ?? null
}

async function assinaturaAtual(): Promise<PushSubscription | null> {
  const registro = await registroPush()
  if (!registro) return null
  return registro.pushManager.getSubscription()
}

export async function estadoPush(): Promise<EstadoPush> {
  if (!pushSuportado()) return 'nao_suportado'
  if (Notification.permission === 'denied') return 'negado'
  const assinatura = await assinaturaAtual()
  return assinatura ? 'ativo' : 'inativo'
}

export async function ativarPush(api: ApiSera, pessoaId: string): Promise<EstadoPush> {
  if (!pushSuportado()) return 'nao_suportado'

  const permissao = await Notification.requestPermission()
  if (permissao !== 'granted') return 'negado'

  const { chave } = await api.chaveNotificacoes()
  // O service worker do PWA já está registrado em /; ele carrega
  // push-handlers.js via importScripts e atende as notificações.
  const registro = await Promise.race([
    navigator.serviceWorker.ready,
    new Promise<null>((resolver) => window.setTimeout(() => resolver(null), 6000)),
  ])
  if (!registro) {
    throw new Error('O aplicativo ainda não terminou de instalar. Recarregue.')
  }

  let assinatura = await registro.pushManager.getSubscription()
  if (!assinatura) {
    assinatura = await registro.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: chaveParaBytes(chave),
    })
  }

  const json = assinatura.toJSON()
  if (!json.endpoint || !json.keys?.p256dh || !json.keys.auth) {
    throw new Error('O navegador não devolveu a inscrição de notificação.')
  }

  await api.inscreverNotificacoes(pessoaId, {
    endpoint: json.endpoint,
    keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
    user_agent: navigator.userAgent.slice(0, 300),
  })
  return 'ativo'
}

export async function desativarPush(
  api: ApiSera,
  pessoaId: string,
): Promise<EstadoPush> {
  if (!pushSuportado()) return 'nao_suportado'
  const assinatura = await assinaturaAtual()
  if (assinatura) {
    await api.removerNotificacoes(pessoaId, assinatura.endpoint).catch(() => undefined)
    await assinatura.unsubscribe()
  }
  return 'inativo'
}
