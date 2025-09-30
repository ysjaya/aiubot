// This is a basic service worker file.
// You can expand it later for caching strategies.
self.addEventListener('install', (event) => {
  console.log('Service Worker installing.');
});

self.addEventListener('fetch', (event) => {
  // Basic fetch handler, passes request through.
  event.respondWith(fetch(event.request));
});
