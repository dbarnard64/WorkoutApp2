/* Iron Log offline cache — v2, network-first.
   Fresh file whenever there is signal, cached copy when there is not.
   Activating this version deletes the v1 cache, which unpins any stale page. */
const CACHE = "ironlog-v2";
const TIMEOUT = 4000;

function fetchWithTimeout(req) {
  return new Promise(function (resolve, reject) {
    const t = setTimeout(function () {
      reject(new Error("timeout"));
    }, TIMEOUT);
    fetch(req).then(
      function (r) {
        clearTimeout(t);
        resolve(r);
      },
      function (e) {
        clearTimeout(t);
        reject(e);
      }
    );
  });
}

self.addEventListener("install", function (e) {
  self.skipWaiting();
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches
      .keys()
      .then(function (ks) {
        return Promise.all(
          ks.filter(function (k) {
            return k !== CACHE;
          }).map(function (k) {
            return caches.delete(k);
          })
        );
      })
      .then(function () {
        return self.clients.claim();
      })
  );
});

self.addEventListener("fetch", function (e) {
  if (e.request.method !== "GET") return;
  e.respondWith(
    fetchWithTimeout(e.request)
      .then(function (res) {
        if (res && res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then(function (c) {
            c.put(e.request, copy);
          });
        }
        return res;
      })
      .catch(function (err) {
        return caches.match(e.request, { ignoreSearch: true }).then(function (hit) {
          if (hit) return hit;
          throw err;
        });
      })
  );
});
