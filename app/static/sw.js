const CACHE_NAME = 'notes-v3';
const APP_SHELL = [
  '/dashboard',
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/js/annotation.js',
  '/static/manifest.json',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Let the browser handle writes normally. app.js queues failed API writes
  // in IndexedDB and retries them when the connection returns.
  if (event.request.method !== 'GET') return;

  // Only handle same-origin http(s) requests.
  if ((url.protocol !== 'http:' && url.protocol !== 'https:') ||
      url.origin !== self.location.origin) return;

  // Network-first for API reads; never cache personal note JSON.
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request).catch(() =>
        new Response(JSON.stringify({ error: 'offline' }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' }
        })
      )
    );
    return;
  }

  const isAppShell = event.request.mode === 'navigate' ||
    url.pathname.startsWith('/static/');
  const isNoteMedia = url.pathname.startsWith('/media/');
  if (!isAppShell && !isNoteMedia) return;

  // Network-first keeps rich-text fixes and other deployments fresh while
  // retaining the last good response for offline use.
  event.respondWith(
    fetch(event.request).then(response => {
      if (response.ok) {
        const clone = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
      }
      return response;
    }).catch(() =>
      caches.match(event.request).then(cached =>
        cached || new Response('Offline', { status: 503 })
      )
    )
  );
});
