const CACHE_NAME = 'notes-v2';
const APP_SHELL = [
  '/dashboard',
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/js/sync.js',
  '/static/js/annotation.js',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png'
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

  // API calls: network-first, fall through to offline response on failure
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request).catch(() =>
        new Response(JSON.stringify({ error: 'Offline', offline: true }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' }
        })
      )
    );
    return;
  }

  // Media files: cache-first (images already uploaded are safe to cache)
  if (url.pathname.startsWith('/media/')) {
    event.respondWith(
      caches.match(event.request).then(cached => {
        if (cached) return cached;
        return fetch(event.request).then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          }
          return response;
        }).catch(() => new Response('', { status: 503 }));
      })
    );
    return;
  }

  // App shell and static assets: cache-first with network fallback
  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;
      return fetch(event.request).then(response => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      }).catch(() => caches.match('/dashboard'));
    })
  );
});
