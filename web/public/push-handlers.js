/* Handlers de notificação importados pelo service worker do PWA.
 * O arquivo é carregado com importScripts no sw.js gerado pelo Workbox. */

// Só aceita caminho interno: nunca navega para outro domínio a partir de
// um payload de push.
function urlSegura(valor) {
  if (typeof valor !== 'string') return '/agenda'
  if (!valor.startsWith('/') || valor.startsWith('//')) return '/agenda'
  return valor
}

self.addEventListener('push', (evento) => {
  let dados = {}
  try {
    dados = evento.data ? evento.data.json() : {}
  } catch {
    dados = { corpo: evento.data ? evento.data.text() : '' }
  }

  const titulo = dados.titulo || 'Sera'
  const opcoes = {
    body: dados.corpo || '',
    icon: '/icons/icon-192-v2.png',
    badge: '/icons/icon-192-v2.png',
    tag: dados.tag || undefined,
    renotify: Boolean(dados.tag),
    data: { url: urlSegura(dados.url) },
  }

  evento.waitUntil(
    (async () => {
      // Resposta de chat: se a conversa já está aberta e visível, o polling
      // atualiza a tela; não vale duplicar com uma notificação.
      if (dados.tipo === 'mensagem') {
        const janelas = await self.clients.matchAll({
          type: 'window',
          includeUncontrolled: true,
        })
        const alvo = dados.url || ''
        const vendo = janelas.some(
          (janela) =>
            janela.visibilityState === 'visible' &&
            (!alvo || janela.url.includes(alvo)),
        )
        if (vendo) return
      }
      await self.registration.showNotification(titulo, opcoes)
    })(),
  )
})

self.addEventListener('notificationclick', (evento) => {
  evento.notification.close()
  const url = urlSegura(evento.notification.data && evento.notification.data.url)

  evento.waitUntil(
    (async () => {
      const janelas = await self.clients.matchAll({
        type: 'window',
        includeUncontrolled: true,
      })
      for (const janela of janelas) {
        if ('focus' in janela) {
          await janela.focus()
          if ('navigate' in janela) await janela.navigate(url)
          return
        }
      }
      if (self.clients.openWindow) await self.clients.openWindow(url)
    })(),
  )
})
