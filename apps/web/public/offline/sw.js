// Increment when any shell asset changes. Never cache workspace pages, API calls or packs.
const CACHE = "langai-offline-shell-v1";
const ASSETS = [
  "index.html",
  "style.css",
  "app.js",
  "matcher.mjs",
  "worker.js",
  "manifest.webmanifest",
  "icon.svg",
  "icon-192.png",
  "icon-512.png",
];
const urls = ASSETS.map((path) => new URL(path, self.registration.scope).href);
self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE);
      await cache.addAll(
        urls.map(
          (url) => new Request(url, { cache: "reload", credentials: "omit" }),
        ),
      );
      // New shells activate after older windows close, keeping worker / matcher versions together.
    })(),
  );
});
self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      for (const key of await caches.keys())
        if (key.startsWith("langai-offline-shell-") && key !== CACHE)
          await caches.delete(key);
      await self.clients.claim();
    })(),
  );
});
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET" || !urls.includes(event.request.url))
    return;
  event.respondWith(
    (async () => {
      const cached = await (await caches.open(CACHE)).match(event.request.url);
      return cached || fetch(event.request);
    })(),
  );
});
