// Ferry Forecast PWA Service Worker
const CACHE_NAME = 'ferry-forecast-v1';
const RUNTIME_CACHE = 'ferry-forecast-runtime';

// Assets to cache on install
const PRECACHE_ASSETS = [
  '/',
  '/static/manifest.json',
  '/static/icon-192.png',
  '/static/icon-512.png'
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
  console.log('[ServiceWorker] Installing...');

  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[ServiceWorker] Caching static assets');
        return cache.addAll(PRECACHE_ASSETS);
      })
      .then(() => {
        console.log('[ServiceWorker] Installation complete');
        return self.skipWaiting();
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[ServiceWorker] Activating...');

  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME && cacheName !== RUNTIME_CACHE) {
            console.log('[ServiceWorker] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      console.log('[ServiceWorker] Activation complete');
      return self.clients.claim();
    })
  );
});

// Fetch event - network first, fallback to cache
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip cross-origin requests
  if (url.origin !== location.origin) {
    return;
  }

  // API requests - network first strategy
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      networkFirstStrategy(request)
    );
    return;
  }

  // Static assets - cache first strategy
  event.respondWith(
    cacheFirstStrategy(request)
  );
});

// Network first strategy (for API calls)
async function networkFirstStrategy(request) {
  const cache = await caches.open(RUNTIME_CACHE);

  try {
    const networkResponse = await fetch(request);

    // Cache successful API responses
    if (networkResponse.ok) {
      cache.put(request, networkResponse.clone());
    }

    return networkResponse;
  } catch (error) {
    console.log('[ServiceWorker] Network request failed, trying cache:', error);

    const cachedResponse = await cache.match(request);

    if (cachedResponse) {
      return cachedResponse;
    }

    // Return offline fallback
    return new Response(
      JSON.stringify({
        error: 'オフラインです。最後に取得したデータがない場合は、インターネット接続を確認してください。'
      }),
      {
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
}

// Cache first strategy (for static assets)
async function cacheFirstStrategy(request) {
  const cachedResponse = await caches.match(request);

  if (cachedResponse) {
    return cachedResponse;
  }

  try {
    const networkResponse = await fetch(request);

    if (networkResponse.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, networkResponse.clone());
    }

    return networkResponse;
  } catch (error) {
    console.log('[ServiceWorker] Failed to fetch:', request.url, error);

    // Return offline page for navigation requests
    if (request.destination === 'document') {
      return new Response(
        `<!DOCTYPE html>
        <html lang="ja">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>オフライン - フェリー予報</title>
          <style>
            body {
              font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
              display: flex;
              justify-content: center;
              align-items: center;
              height: 100vh;
              margin: 0;
              background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
              color: white;
              text-align: center;
              padding: 20px;
            }
            h1 { font-size: 2em; margin-bottom: 20px; }
            p { font-size: 1.1em; line-height: 1.6; }
            button {
              margin-top: 30px;
              padding: 15px 30px;
              font-size: 1em;
              background: white;
              color: #667eea;
              border: none;
              border-radius: 25px;
              cursor: pointer;
              font-weight: bold;
            }
          </style>
        </head>
        <body>
          <div>
            <h1>📡 オフラインです</h1>
            <p>インターネット接続を確認してください。<br>接続後、自動的に最新データを取得します。</p>
            <button onclick="location.reload()">再試行</button>
          </div>
        </body>
        </html>`,
        {
          headers: { 'Content-Type': 'text/html' }
        }
      );
    }

    throw error;
  }
}

// Background sync for notifications
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-forecast') {
    console.log('[ServiceWorker] Background sync triggered');
    event.waitUntil(syncForecastData());
  }
});

async function syncForecastData() {
  try {
    const response = await fetch('/api/forecast');
    if (response.ok) {
      const cache = await caches.open(RUNTIME_CACHE);
      cache.put('/api/forecast', response);
      console.log('[ServiceWorker] Forecast data synced');
    }
  } catch (error) {
    console.log('[ServiceWorker] Background sync failed:', error);
  }
}

// Push notifications
self.addEventListener('push', (event) => {
  console.log('[ServiceWorker] Push notification received');

  const data = event.data ? event.data.json() : {};
  const title = data.title || '🚢 フェリー欠航警報';
  const options = {
    body: data.body || '高リスク日が検出されました',
    icon: '/static/icon-192.png',
    badge: '/static/icon-192.png',
    vibrate: [200, 100, 200],
    data: {
      url: data.url || '/'
    },
    actions: [
      {
        action: 'view',
        title: '予報を見る'
      },
      {
        action: 'close',
        title: '閉じる'
      }
    ]
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

// Notification click handler
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'view') {
    const url = event.notification.data.url;
    event.waitUntil(
      clients.openWindow(url)
    );
  }
});

console.log('[ServiceWorker] Script loaded');
