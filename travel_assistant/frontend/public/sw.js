/* Travel Assistant offline service worker.
   Caches the app shell so the pinned "Travel Assistant (Offline)" icon
   opens even when Home Assistant is unreachable. */
const CACHE = 'ta-offline-v1'

self.addEventListener('install', (event) => {
  self.skipWaiting()
  event.waitUntil(caches.open(CACHE))
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  )
})

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return

  // Navigations (the offline app page): network first, fall back to cache
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone()
          caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {})
          return res
        })
        .catch(() => caches.match(req).then((hit) => hit || caches.match(new URL('./', self.location).href)))
    )
    return
  }

  const url = new URL(req.url)
  // Cache static app assets (JS/CSS/icons) so the shell works offline
  if (url.pathname.includes('/static/react/') || url.pathname.includes('/assets/')) {
    event.respondWith(
      caches.match(req).then((hit) => {
        const fetched = fetch(req)
          .then((res) => {
            if (res && res.ok) {
              const copy = res.clone()
              caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {})
            }
            return res
          })
          .catch(() => hit)
        return hit || fetched
      })
    )
  }
})
