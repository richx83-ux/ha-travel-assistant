/* Travel Assistant offline service worker.
   Caches the app shell so the pinned icon opens with no Home Assistant connection.
   Never caches 401/403 (Ingress auth failures) and falls back to the shell instead. */
const CACHE = 'ta-offline-v8'

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
  // Only the HTML shell — never a CSS/JS file under /static/react/
  const html = keys.find((k) => {
    const u = k.url.split('?')[0]
    return (u.endsWith('/react') || u.endsWith('/react/') || u.endsWith('index.html')) && !u.includes('/static/')
  })
  return html ? cache.match(html) : null
}

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)

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
        // Let Home Assistant handle login — do not hide 401/redirect behind a cached page
        if (res.status === 401 || res.status === 403 || (res.status >= 300 && res.status < 400)) {
          return res
        }
        const hit = await fromCache(req) || await cachedShell()
        if (hit) return hit
        return res
      } catch (e) {
        const hit = await fromCache(req) || await cachedShell()
        if (hit) return hit
        return new Response('<!doctype html><title>Offline</title><body><h1>Travel Assistant (Offline)</h1><p>Open once while online, then try again.</p></body>', { headers: { 'Content-Type': 'text/html' } })
      }
    })())
    return
  }

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
