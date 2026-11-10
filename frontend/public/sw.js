// MedWise BD service worker: offline copies of pages, with freshness first.
//
// - Pages (navigations) and GET /api/* data: network first. Every 200 answer is saved with the
//   time it was saved; without a network the saved copy is served (marked with a
//   <meta name="medwise-saved-at"> so the page can say how old it is), else /offline.html.
// - Next.js files under /_next/static/ never change (their names hold a hash): cache first, as are
//   the app icons and manifest.
// - Never saved: POST and other non-GET requests, search, health, prescription reading, the
//   medicine request log, Next.js client navigation data (?_rsc), other sites and non-200 answers.
// - A saved page keeps the response headers it came with, including its Content-Security-Policy,
//   so the nonce in the header still matches the nonce on the page's own scripts.
// - Caps: 100 saved pages/data, 300 static files; the oldest saved goes first.
// - "Save all medicines for offline use" sends {type: "save-all", urls} with a MessagePort;
//   progress and the result come back on the port.

const VERSION = "v2";
const PAGES = `medwise-pages-${VERSION}`; // keep in sync with src/lib/offline.ts
const ASSETS = `medwise-assets-${VERSION}`;
const SHELL = `medwise-offline-${VERSION}`;
const OFFLINE_URL = "/offline.html";
const MAX_PAGES = 100;
const MAX_ASSETS = 300;
const SAVED_AT = "x-medwise-saved-at";
const NEVER_SAVE = /^\/api\/(search|health|prescription|requests)(\/|$)/;
// App icons and the manifest change only with a new deploy (the icon URL carries a hash).
const APP_FILES = /^\/(icon\.svg|apple-icon\.png|manifest\.webmanifest|icons\/)/;

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL).then((cache) => cache.addAll([OFFLINE_URL, "/icons/icon-192.png"])));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  const keep = new Set([PAGES, ASSETS, SHELL]);
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => !keep.has(key)).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.searchParams.has("_rsc") || request.headers.get("RSC")) return; // let Next.js fall back
  if (NEVER_SAVE.test(url.pathname)) return;

  if (url.pathname.startsWith("/_next/static/") || APP_FILES.test(url.pathname)) {
    event.respondWith(cacheFirst(request));
  } else if (request.mode === "navigate") {
    event.respondWith(networkFirst(event, { page: true }));
  } else if (url.pathname.startsWith("/api/")) {
    event.respondWith(networkFirst(event, { page: false }));
  }
});

self.addEventListener("message", (event) => {
  if (event.data?.type === "save-all" && event.ports[0]) {
    event.waitUntil(saveAll(event.data.urls, event.ports[0]));
  }
});

function keyFor(url) {
  const u = new URL(url, self.location.origin);
  return u.origin + u.pathname + u.search; // no #fragment
}

/** A copy of `response` with our own headers (the body is already decoded). */
function rebuild(body, response, extraHeaders) {
  const headers = new Headers(response.headers);
  // The body is stored decoded and whole; drop headers that described the original transfer.
  for (const name of ["content-encoding", "content-length", "transfer-encoding", "connection", "keep-alive"]) {
    headers.delete(name);
  }
  for (const [name, value] of Object.entries(extraHeaders)) headers.set(name, value);
  return new Response(body, { status: response.status, statusText: response.statusText, headers });
}

async function trim(cacheName, max) {
  const cache = await caches.open(cacheName);
  const keys = await cache.keys(); // oldest first: put() moves an entry to the end
  await Promise.all(keys.slice(0, Math.max(0, keys.length - max)).map((key) => cache.delete(key)));
}

async function save(url, response) {
  if (response.status !== 200 || response.type !== "basic") return;
  const body = await response.arrayBuffer();
  const cache = await caches.open(PAGES);
  await cache.delete(keyFor(url)); // re-saving moves it to the newest end
  await cache.put(keyFor(url), rebuild(body, response, { [SAVED_AT]: new Date().toISOString() }));
  await trim(PAGES, MAX_PAGES);
}

async function networkFirst(event, { page }) {
  const request = event.request;
  try {
    const response = await fetch(request);
    // Save in the background: the page is shown as soon as it arrives.
    event.waitUntil(save(request.url, response.clone()).catch(() => {}));
    return response;
  } catch {
    const cached = await caches.match(keyFor(request.url), { cacheName: PAGES });
    if (cached) return page ? markSaved(cached) : cached;
    if (page) return (await caches.match(OFFLINE_URL, { cacheName: SHELL })) ?? Response.error();
    return Response.error();
  }
}

/** Serve a saved page with a <meta> giving the time it was saved (no script, so no CSP change). */
async function markSaved(cached) {
  const savedAt = cached.headers.get(SAVED_AT) ?? "";
  const html = await cached.text();
  const meta = `<meta name="medwise-saved-at" content="${savedAt.replace(/[^0-9TZ:.\-]/g, "")}">`;
  const marked = /<head[^>]*>/i.test(html) ? html.replace(/<head[^>]*>/i, (head) => head + meta) : meta + html;
  return rebuild(marked, cached, {});
}

async function cacheFirst(request) {
  const cached = await caches.match(request, { cacheName: ASSETS });
  if (cached) return cached;
  const response = await fetch(request);
  if (response.status === 200 && response.type === "basic") {
    const cache = await caches.open(ASSETS);
    await cache.put(request, response.clone());
    await trim(ASSETS, MAX_ASSETS);
  }
  return response;
}

/** The /_next/static/ files a saved page needs, so it renders offline even after a new deploy. */
function staticFiles(html) {
  const found = new Set();
  for (const match of html.matchAll(/["'(](\/_next\/static\/[^"'()\s\\]+)/g)) found.add(match[1]);
  return [...found];
}

async function saveAll(urls, port) {
  let saved = 0;
  let failed = 0;
  const assets = new Set();
  for (const url of urls) {
    try {
      const response = await fetch(url, { credentials: "same-origin", headers: { Accept: "text/html" } });
      if (response.status !== 200) throw new Error(String(response.status));
      await save(url, response.clone());
      for (const file of staticFiles(await response.text())) assets.add(file);
      saved += 1;
    } catch {
      failed += 1;
    }
    port.postMessage({ type: "progress", done: saved + failed, total: urls.length });
  }
  const assetCache = await caches.open(ASSETS);
  for (const file of assets) {
    if (await assetCache.match(file)) continue;
    try {
      const response = await fetch(file);
      if (response.status === 200) await assetCache.put(file, response);
    } catch {
      // A missing static file only matters offline; the page itself is saved.
    }
  }
  await trim(ASSETS, MAX_ASSETS);
  port.postMessage({ type: "done", saved, failed, total: urls.length });
}
