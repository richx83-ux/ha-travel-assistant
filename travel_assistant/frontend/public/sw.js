/* Travel Assistant offline service worker.
   Caches the app shell so the pinned icon opens with no Home Assistant connection. */
const CACHE = 'ta-offline-v2'

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

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)

  // App navigations: network first, then any cached copy of this path
  if (req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html')) {
    event.respondWith((async () => {
      try {
        const res = await fetch(req)
        const copy = res.clone()
        const cache = await caches.open(CACHE)
        await cache.put(req, copy)
        await cache.put(url.pathname, res.clone())
        return res
      } catch (e) {
        const hit = await fromCache(req)
        if (hit) return hit
        const cache = await caches.open(CACHE)
        const keys = await cache.keys()
        const html = keys.find((k) => k.url.includes('/react'))
        if (html) return cache.match(html)
        return new Response(
          '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><title>Offline</title><body style="font-family:system-ui;padding:1.5rem"><h1>Travel Assistant (Offline)</h1><p>This page is not cached yet. Open it once while online, then try again.</p></body>',
          { headers: { 'Content-Type': 'text/html' } }
        )
      }
    })())
    return
  }

  // Static app assets
  if (url.pathname.includes('/static/react/') || url.pathname.includes('/assets/')) {
    event.respondWith((async () => {
      const hit = await fromCache(req)
      try {
        const res = await fetch(req)
        if (res && res.ok) {
          const cache = await caches.open(CACHE)
          await cache.put(req, res.clone())
        }
        return res
      } catch (e) {
        if (hit) return hit
        throw e
      }
    })())
  }
})

// Page can ask the SW to cache specific URLs
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
