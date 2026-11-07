/* Travel Assistant offline service worker.
   Caches the app shell so the pinned icon opens with no Home Assistant connection.
   Never caches 401/403 (Ingress auth failures) and falls back to the shell instead. */
const CACHE = 'ta-offline-v3'

self.addEventListener('install', (event) => {
  self.skipWaiting()
  event.waitUntil(caches.open(CACHE))
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  )
})

async function fromCache(request) {
  const cache = await caches.open(CACHE)
  return (await cache.match(request)) || (await cache.match(request, { ignoreSearch: true }))
}

async function cachedShell() {
  const cache = await caches.open(CACHE)
  const keys = await cache.keys()
  const html = keys.find((k) => k.url.includes('/react'))
  return html ? cache.match(html) : null
}

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)

  // App navigations: network first, but a 401/403 (Ingress not logged in) must not replace the shell
  if (req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html')) {
    event.respondWith((async () => {
      try {
        const res = await fetch(req)
        if (res.ok) {
          const cache = await caches.open(CACHE)
          await cache.put(req, res.clone())
          await cache.put(url.pathname, res.clone())
          return res
        }
        // 401/403 or other error: use the cached app so the offline UI still opens
        const hit = await fromCache(req) || await cachedShell()
        if (hit) return hit
        return res
      } catch (e) {
        const hit = await fromCache(req) || await cachedShell()
        if (hit) return hit
        return new Response(
          '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><title>Offline</title><body style="font-family:system-ui;padding:1.5rem"><h1>Travel Assistant (Offline)</h1><p>This page is not cached yet. Open it once while online and logged in, then try again.</p></body>',
          { headers: { 'Content-Type': 'text/html' } }
        )
      }
    })())
    return
  }

  // Static app assets: cache only successful responses
  if (url.pathname.includes('/static/react/') || url.pathname.includes('/assets/')) {
    event.respondWith((async () => {
      const hit = await fromCache(req)
      try {
        const res = await fetch(req)
        if (res && res.ok) {
          const cache = await caches.open(CACHE)
          await cache.put(req, res.clone())
          return res
        }
        return hit || res
      } catch (e) {
        if (hit) return hit
        throw e
      }
    })())
  }
})

self.addEventListener('message', (event) => {
  const data = event.data || {}
  if (data.type === 'CACHE_URLS' && Array.isArray(data.urls)) {
    event.waitUntil((async () => {
      const cache = await caches.open(CACHE)
      await Promise.all(data.urls.map(async (u) => {
        try {
          const res = await fetch(u, { credentials: 'same-origin' })
          if (res && res.ok) await cache.put(u, res.clone())
        } catch (e) {}
      }))
      if (event.source) event.source.postMessage({ type: 'CACHED' })
    })())
  }
})
