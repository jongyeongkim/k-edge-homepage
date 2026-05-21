<<<<<<< HEAD
self.addEventListener("install", (event) => {
=======
const CACHE_NAME = "k-edge-pwa-v3";
const CORE_ASSETS = ["/", "/index.html", "/style.css", "/script.js", "/manifest.json", "/icon-192.png", "/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(CORE_ASSETS)).catch(() => null));
>>>>>>> 40bbb150c4309704c4b73516f27458abc3bf6854
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
<<<<<<< HEAD
  event.waitUntil(clients.claim());
});

self.addEventListener("fetch", (event) => {
});
=======
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy)).catch(() => null);
        return response;
      })
      .catch(() => caches.match(event.request).then((cached) => cached || caches.match("/index.html")))
  );
});
>>>>>>> 40bbb150c4309704c4b73516f27458abc3bf6854
