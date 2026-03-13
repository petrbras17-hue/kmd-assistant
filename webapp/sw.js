// =============================================================================
// KMD Assistant — Service Worker
// Production PWA service worker for ALDMEGA LAB aluminum construction checker
// =============================================================================

// ---------------------------------------------------------------------------
// 1. Cache name versioning
//    Bump the version suffix when deploying new assets so the ACTIVATE event
//    purges stale caches automatically.
// ---------------------------------------------------------------------------
const CACHE_STATIC  = 'kmd-v1';
const CACHE_API     = 'kmd-api-v1';   // reserved name; API responses are NOT cached
const CACHE_FONTS   = 'kmd-fonts-v1';

const EXPECTED_CACHES = new Set([CACHE_STATIC, CACHE_API, CACHE_FONTS]);

// ---------------------------------------------------------------------------
// 2. Assets to pre-cache during INSTALL
// ---------------------------------------------------------------------------
const PRECACHE_URLS = [
  // App shell
  '/',
  '/offline.html',

  // Tailwind CSS (runtime build via CDN)
  'https://cdn.tailwindcss.com',

  // Alpine.js
  'https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js',

  // Three.js core module + common addons loader entry
  'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js',

  // Google Fonts CSS (the CSS itself; actual font files are cache-first later)
  'https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400;1,500&family=Instrument+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap',
];

// ---------------------------------------------------------------------------
// 3. Expiry helpers
// ---------------------------------------------------------------------------
const SEVEN_DAYS_MS  = 7  * 24 * 60 * 60 * 1000;
const THIRTY_DAYS_MS = 30 * 24 * 60 * 60 * 1000;

/**
 * Store a response in the given cache together with a timestamp header
 * so we can enforce time-based expiry on cache-first strategies.
 */
async function cacheWithTimestamp(cacheName, request, response) {
  const cache = await caches.open(cacheName);
  const headers = new Headers(response.headers);
  headers.set('sw-cache-timestamp', Date.now().toString());
  const timestampedResponse = new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
  await cache.put(request, timestampedResponse);
}

/**
 * Returns true if the cached response is older than `maxAgeMs`.
 */
function isCacheExpired(response, maxAgeMs) {
  const timestamp = response.headers.get('sw-cache-timestamp');
  if (!timestamp) return true; // no timestamp → treat as expired
  return (Date.now() - Number(timestamp)) > maxAgeMs;
}

// ---------------------------------------------------------------------------
// 4. INSTALL — pre-cache critical assets, then immediately activate
// ---------------------------------------------------------------------------
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_STATIC)
      .then((cache) => {
        // Use addAll for same-origin assets, individual fetch for cross-origin
        // because some CDN responses may be opaque (no-cors).
        const cachePromises = PRECACHE_URLS.map((url) => {
          const request = new Request(url, { mode: 'cors' });
          return fetch(request)
            .then((response) => {
              if (!response.ok && response.type !== 'opaque') {
                // Non-critical: log but don't break install for CDN hiccups
                console.warn(`[SW] Pre-cache failed for ${url}: ${response.status}`);
                return;
              }
              return cache.put(url, response);
            })
            .catch((err) => {
              // Network may be unavailable during install — log and continue.
              // The asset will be cached on first use via runtime strategies.
              console.warn(`[SW] Pre-cache network error for ${url}:`, err.message);
            });
        });
        return Promise.all(cachePromises);
      })
      .then(() => self.skipWaiting()) // activate immediately
  );
});

// ---------------------------------------------------------------------------
// 5. ACTIVATE — purge old caches that no longer match current version names
// ---------------------------------------------------------------------------
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((cacheNames) =>
        Promise.all(
          cacheNames
            .filter((name) => !EXPECTED_CACHES.has(name))
            .map((name) => {
              console.info(`[SW] Deleting old cache: ${name}`);
              return caches.delete(name);
            })
        )
      )
      .then(() => self.clients.claim()) // take control of all open tabs
  );
});

// ---------------------------------------------------------------------------
// 6. FETCH — routing and caching strategies
// ---------------------------------------------------------------------------
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // --- 6a. API calls: network-only, never cache ----------------------------
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/api')) {
    event.respondWith(
      fetch(request).catch(() =>
        new Response(
          JSON.stringify({ error: 'offline', message: 'Network unavailable' }),
          { status: 503, headers: { 'Content-Type': 'application/json' } }
        )
      )
    );
    return;
  }

  // --- 6b. Google Fonts: cache-first, 30-day expiry ------------------------
  if (
    url.hostname === 'fonts.googleapis.com' ||
    url.hostname === 'fonts.gstatic.com'
  ) {
    event.respondWith(cacheFirstWithExpiry(request, CACHE_FONTS, THIRTY_DAYS_MS));
    return;
  }

  // --- 6c. CDN assets: cache-first, 7-day expiry --------------------------
  if (url.hostname === 'cdn.jsdelivr.net' || url.hostname === 'cdn.tailwindcss.com') {
    event.respondWith(cacheFirstWithExpiry(request, CACHE_STATIC, SEVEN_DAYS_MS));
    return;
  }

  // --- 6d. Navigation requests: network-first → cache → offline.html ------
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Cache the latest version of the page for offline use
          const clone = response.clone();
          caches.open(CACHE_STATIC).then((cache) => cache.put(request, clone));
          return response;
        })
        .catch(() =>
          caches.match(request).then(
            (cached) => cached || caches.match('/offline.html')
          )
        )
    );
    return;
  }

  // --- 6e. Static assets (CSS, JS, images): stale-while-revalidate --------
  if (isStaticAsset(request)) {
    event.respondWith(staleWhileRevalidate(request, CACHE_STATIC));
    return;
  }

  // --- 6f. Everything else: network with cache fallback --------------------
  event.respondWith(
    fetch(request).catch(() => caches.match(request))
  );
});

// ---------------------------------------------------------------------------
// 7. Strategy implementations
// ---------------------------------------------------------------------------

/**
 * Cache-first with time-based expiry.
 * Returns the cached response if it exists and is not expired; otherwise
 * fetches from network, caches the result, and returns it.
 */
async function cacheFirstWithExpiry(request, cacheName, maxAgeMs) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  if (cached && !isCacheExpired(cached, maxAgeMs)) {
    return cached;
  }

  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok || networkResponse.type === 'opaque') {
      await cacheWithTimestamp(cacheName, request, networkResponse.clone());
    }
    return networkResponse;
  } catch (err) {
    // Network failed — return stale cache (better than nothing)
    if (cached) return cached;
    throw err;
  }
}

/**
 * Stale-while-revalidate: serve from cache immediately, but fetch an update
 * in the background so next load gets the fresh version.
 */
async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  // Fire-and-forget network update
  const networkFetch = fetch(request)
    .then((response) => {
      if (response.ok || response.type === 'opaque') {
        cache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => null);

  // Return cached version immediately if available; otherwise wait for network
  return cached || (await networkFetch) || new Response('', { status: 504 });
}

/**
 * Determines if a request targets a static asset based on URL path extension.
 */
function isStaticAsset(request) {
  const url = new URL(request.url);
  return /\.(css|js|mjs|png|jpg|jpeg|gif|svg|webp|avif|ico|woff2?|ttf|eot)(\?.*)?$/i
    .test(url.pathname);
}

// ---------------------------------------------------------------------------
// 8. Background Sync — placeholder for offline form submissions
//    Register a sync event so queued form data (e.g. KMD check submissions)
//    can be replayed once connectivity is restored.
// ---------------------------------------------------------------------------
self.addEventListener('sync', (event) => {
  if (event.tag === 'kmd-offline-submission') {
    event.waitUntil(replayOfflineSubmissions());
  }
});

/**
 * Replay queued submissions stored in IndexedDB by the main app.
 * The main app is responsible for writing to the 'kmd-offline-queue' object
 * store; this worker reads and replays them.
 */
async function replayOfflineSubmissions() {
  try {
    const db = await openOfflineDB();
    const tx = db.transaction('requests', 'readwrite');
    const store = tx.objectStore('requests');
    const allRequests = await idbGetAll(store);

    for (const entry of allRequests) {
      try {
        const response = await fetch(entry.url, {
          method: entry.method || 'POST',
          headers: entry.headers || { 'Content-Type': 'application/json' },
          body: entry.body,
        });
        if (response.ok) {
          store.delete(entry.id);
        }
      } catch {
        // Still offline for this entry — leave it in the queue
        break;
      }
    }
  } catch (err) {
    console.error('[SW] Background sync replay failed:', err);
  }
}

/**
 * Open (or create) the IndexedDB database used for offline queue.
 */
function openOfflineDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('kmd-offline-queue', 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains('requests')) {
        db.createObjectStore('requests', { keyPath: 'id', autoIncrement: true });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

/**
 * Promise wrapper around IDBObjectStore.getAll().
 */
function idbGetAll(store) {
  return new Promise((resolve, reject) => {
    const req = store.getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

// ---------------------------------------------------------------------------
// 9. Self-update mechanism
//    The main app can periodically call navigator.serviceWorker.register()
//    which triggers a byte-level diff check. When a new SW is found the
//    browser installs it in the background. The new SW posts a message to
//    clients so the UI can show an "Update available" banner.
// ---------------------------------------------------------------------------
self.addEventListener('install', () => {
  // Notify all controlled clients that a new version is available
  self.clients.matchAll({ type: 'window' }).then((clients) => {
    clients.forEach((client) => {
      client.postMessage({ type: 'SW_UPDATE_AVAILABLE' });
    });
  });
});

// ---------------------------------------------------------------------------
// 10. Message handler — skipWaiting on demand
//     When the UI confirms the user wants to update, it posts a
//     { type: 'SKIP_WAITING' } message to the waiting SW.
// ---------------------------------------------------------------------------
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }

  // Respond to version queries so the app can display the current SW version
  if (event.data && event.data.type === 'GET_VERSION') {
    event.source.postMessage({
      type: 'SW_VERSION',
      version: CACHE_STATIC, // version string follows the cache name
    });
  }
});
