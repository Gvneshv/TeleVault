/**
 * Minimal service worker: caches the static app shell only.
 *
 * Deliberately does NOT cache /api/* responses.
 * This is a personal archive of private message data — serving stale or cached API responses
 * (especially across the deleted-messages and search endpoints) would be actively misleading, not just stale.
 * Only the shell (HTML/CSS/JS) is cached, so the app *loads* offline;
 * it still needs a live connection to the API to show real data.
 *
 * Bump CACHE_NAME whenever shell files change, so old caches are evicted on the next visit instead of silently serving outdated JS/CSS.
 */

const CACHE_NAME = "televault-shell-v1";
const SHELL_FILES = [
  "/",
  "/index.html",
  "/css/variables.css",
  "/css/base.css",
  "/js/theme.js",
  "/js/i18n.js",
  "/js/app.js",
  "/js/i18n/en.js",
  "/js/i18n/uk.js",
  "/manifest.webmanifest",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_FILES)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== CACHE_NAME)
            .map((key) => caches.delete(key)),
        ),
      ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Never intercept API calls — always go to the network.
  if (url.pathname.startsWith("/api/")) {
    return;
  }

  event.respondWith(
    caches
      .match(event.request)
      .then((cached) => cached || fetch(event.request)),
  );
});
