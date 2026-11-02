/* Handlers de notificação importados pelo service worker do PWA.
 * O arquivo é carregado com importScripts no sw.js gerado pelo Workbox. */

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
    data: { url: dados.url || '/agenda' },
  }

  evento.waitUntil(self.registration.showNotification(titulo, opcoes))
})

self.addEventListener('notificationclick', (evento) => {
  evento.notification.close()
  const url = (evento.notification.data && evento.notification.data.url) || '/agenda'

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
