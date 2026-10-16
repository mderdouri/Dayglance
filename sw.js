const CACHE = 'dayglance-shell-v10';
const CORE = ['./', './index.html', './styles.css', './detail-hours.js', './air-quality.js', './radar.js', './app.js', './manifest.webmanifest', './config.json'];
const CORE_PATHS = new Set(CORE.map(path => new URL(path, self.registration.scope).pathname));
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(CORE)).then(() => self.skipWaiting())));
self.addEventListener('activate', event => event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('dayglance-shell-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim())));
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.origin !== location.origin || url.pathname.startsWith(new URL('./api/', self.registration.scope).pathname) || !CORE_PATHS.has(url.pathname)) return;
  // Revalidate the app shell, but avoid rewriting unchanged files into browser storage.
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const cached = await cache.match(event.request, {ignoreSearch:true});
    try {
      const response = await fetch(event.request);
      if (response.ok && (!cached || !await sameBody(cached, response))) {
        await cache.put(new Request(new URL(url.pathname, url.origin)), response.clone());
      }
      return response;
    } catch {
      return cached || (event.request.mode === 'navigate' ? await cache.match('./index.html') : null) || Response.error();
    }
  })());
});

async function sameBody(first, second) {
  const [left, right] = await Promise.all([first.clone().arrayBuffer(), second.clone().arrayBuffer()]);
  if (left.byteLength !== right.byteLength) return false;
  const a = new Uint8Array(left), b = new Uint8Array(right);
  return a.every((value, index) => value === b[index]);
}
