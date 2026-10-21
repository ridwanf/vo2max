// static/sw.js — cache shell biar sesi terakhir tetap kebuka offline
const SHELL = "vo2max-v3";
const ASSETS = ["/", "/app.js", "/manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== SHELL).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Network-first untuk /api/* (data harus segar), cache-first untuk shell.
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  if (url.pathname.startsWith("/api/")) {
    e.respondWith(fetch(e.request).catch(() => new Response('{"offline":true}', {
      headers: { "Content-Type": "application/json" },
    })));
    return;
  }

  // network-first: update langsung kepakai, cache cuma cadangan offline
  e.respondWith(
    fetch(e.request).then((res) => {
      const copy = res.clone();
      caches.open(SHELL).then((c) => c.put(e.request, copy));
      return res;
    }).catch(() => caches.match(e.request).then((hit) => hit || caches.match("/")))
  );
});
