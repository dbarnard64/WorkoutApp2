/* Iron Log offline cache — v2, network-first.
   Fresh file whenever there is signal, cached copy when there is not.
   Activating this version deletes the v1 cache, which unpins any stale page. */
const CACHE = "ironlog-v3";
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

/* A page cut short by a dropped connection still arrives with status 200. Caching a
   half-written file leaves the app broken on the next launch with a bare "Script error",
   so only store a document that actually reached its closing tag. */
function cacheIfWhole(req, res) {
  const type = res.headers.get("content-type") || "";
  if (type.indexOf("text/html") < 0) {
    const copy = res.clone();
    caches.open(CACHE).then(function (c) {
      c.put(req, copy);
    });
    return;
  }
  res
    .clone()
    .text()
    .then(function (body) {
      if (body.length > 2000 && body.lastIndexOf("</html>") > body.length - 200) {
        caches.open(CACHE).then(function (c) {
          c.put(req, new Response(body, { status: 200, headers: { "content-type": type } }));
        });
      }
    })
    .catch(function () {});
}

self.addEventListener("fetch", function (e) {
  if (e.request.method !== "GET") return;
  e.respondWith(
    fetchWithTimeout(e.request)
      .then(function (res) {
        if (res && res.ok) cacheIfWhole(e.request, res);
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
