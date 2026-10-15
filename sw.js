const CACHE = 'dayglance-shell-v4';
const CORE = ['./', './index.html', './styles.css', './app.js', './manifest.webmanifest', './config.json'];
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(CORE)).then(() => self.skipWaiting())));
self.addEventListener('activate', event => event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('dayglance-shell-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim())));
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.origin !== location.origin) return;
  // Prefer deployed files on reload; retain the shell as an offline fallback.
  event.respondWith(fetch(event.request).then(async response => {
    if (response.ok) await (await caches.open(CACHE)).put(event.request, response.clone());
    return response;
  }).catch(async () => (await caches.match(event.request)) ||
    (event.request.mode === 'navigate' ? await caches.match('./index.html') : null) || Response.error()));
});
