/* Service worker: makes the cleaner work with the network switched off.
 *
 * It only ever touches same-origin requests for static assets. Photo data is
 * never sent anywhere — the app keeps everything in memory for the duration of
 * the tab, and the one cache that can briefly hold a shared photo is emptied
 * as soon as the page picks it up.
 */
const VERSION = "imc-v1"; // replaced with the commit id by the Pages workflow
const SHARE_CACHE = "imc-shared";
// While developing, always prefer the network: otherwise a cache-first service
// worker happily serves yesterday's app.js and an edit looks like it did nothing.
const DEV = self.location.hostname === "localhost" || self.location.hostname === "127.0.0.1";
const PRECACHE = [
  "./",
  "./index.html",
  "./styles.css",
  "./app.js",
  "./manifest.json",
  "./icon.svg",
  "./icon-192.png",
  "./icon-512.png",
  "./icon-maskable-512.png",
  "./apple-touch-icon.png",
  "./vendor/jszip.min.js",
  "./vendor/exifr.min.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(VERSION)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== VERSION && k !== SHARE_CACHE).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

/* The operating system shares a photo by POSTing it here (see share_target in
 * manifest.json). We park the bytes in a cache and bounce the user to the app,
 * which reads the cache and clears it. Nothing leaves the device. */
async function acceptShare(request) {
  const url = new URL(request.url);
  const target = new URL("./", self.registration.scope);
  if (url.origin !== self.location.origin || !url.pathname.endsWith("/share")) {
    return Response.error(); // never accept a POST for anywhere but our share target
  }

  try {
    const form = await request.formData();
    const files = form.getAll("photos").filter((f) => f && typeof f !== "string" && f.size > 0);
    const cache = await caches.open(SHARE_CACHE);
    for (const key of await cache.keys()) await cache.delete(key);
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const headers = new Headers({
        "content-type": file.type || "application/octet-stream",
        "x-shared-name": encodeURIComponent(file.name || `shared-${i}`),
      });
      await cache.put(new Request(`./shared/${i}`), new Response(file, { headers }));
    }
  } catch (_) {
    /* fall through to the app, which will report "nothing was shared" */
  }

  target.searchParams.set("shared", "1");
  return new Response(null, { status: 303, headers: { Location: target.href } });
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method === "POST") {
    event.respondWith(acceptShare(req));
    return;
  }
  if (req.method !== "GET") return;
  let url;
  try { url = new URL(req.url); } catch (_) { return; }
  if (url.origin !== self.location.origin) return; // never proxy anything remote

  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).catch(() => caches.match("./index.html").then((r) => r || Response.error()))
    );
    return;
  }

  if (DEV) {
    event.respondWith(fetch(req).catch(() => caches.match(req)));
    return;
  }

  event.respondWith(
    caches.match(req).then((hit) => {
      if (hit) return hit;
      return fetch(req).then((resp) => {
        if (resp && resp.status === 200 && resp.type === "basic") {
          const copy = resp.clone();
          caches.open(VERSION).then((cache) => cache.put(req, copy)).catch(() => {});
        }
        return resp;
      });
    })
  );
});
