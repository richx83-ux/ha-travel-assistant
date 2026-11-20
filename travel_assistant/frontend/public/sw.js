/* Kill switch for the old offline service worker. The offline caching now lives in the
 * Travel Assistant Android app, so this removes the old caches and unregisters itself.
 * Safe to delete once no phone or browser still has it installed. */
self.addEventListener('install', () => self.skipWaiting())

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys()
    await Promise.all(keys.map((k) => caches.delete(k)))
    await self.registration.unregister()
  })())
})
