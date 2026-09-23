/* Iron Log offline cache - stale-while-revalidate for the page.

   The page opens from the copy already stored on the phone, straight away,
   whatever the signal is doing. At the same moment a fresh copy is fetched in
   the background; if it turns out to be a different build it replaces the
   stored one and the open page is told, so it can offer a reload. The network
   is only waited on when nothing is stored yet - the very first launch.

   The previous worker was network-first with a 4 s timeout, so a weak signal
   made every launch wait for the network. It was worse than 4 s in practice:
   the timeout only covered the headers, and once they arrived the rest of the
   ~225 KB page could trickle in at any speed with nothing capping it. Measured
   on a simulated one-bar connection: 5.9 s to open.

   The cache name is unchanged on purpose. The page the previous worker stored
   is picked up as-is, so the first launch under this worker is instant too. */
const CACHE = "ironlog-v3";
const TIMEOUT = 4000;

/* A page cut short by a dropped connection still arrives with status 200.
   Storing a half-written file leaves the app broken on the next launch with a
   bare "Script error", so only a page that reached its closing tag is kept. */
function whole(body) {
  return body.length > 2000 && body.lastIndexOf("</html>") > body.length - 200;
}

function buildOf(html) {
  const m = /<meta name="build" content="([^"]+)"/.exec(html || "");
  return m ? m[1] : null;
}

function isPage(req) {
  return req.mode === "navigate" || (req.headers.get("accept") || "").indexOf("text/html") >= 0;
}

function tell(build) {
  return self.clients.matchAll({ type: "window" }).then(function (cs) {
    cs.forEach(function (c) {
      c.postMessage({ type: "ironlog-update", build: build });
    });
  });
}

/* Store a fresh page if it is whole, and say so if it is a different build
   from the one stored before it. */
function keep(req, res) {
  const type = res.headers.get("content-type") || "text/html; charset=utf-8";
  return res.text().then(function (body) {
    if (!whole(body)) return;
    return caches.open(CACHE).then(function (c) {
      return c
        .match(req, { ignoreSearch: true })
        .then(function (old) {
          return old ? old.text() : "";
        })
        .then(function (was) {
          return c
            .put(req, new Response(body, { status: 200, headers: { "content-type": type } }))
            .then(function () {
              const a = buildOf(was);
              const b = buildOf(body);
              if (a && b && a !== b) return tell(b);
            });
        });
    });
  });
}

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

self.addEventListener("install", function () {
  self.skipWaiting();
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches
      .keys()
      .then(function (ks) {
        return Promise.all(
          ks
            .filter(function (k) {
              return k !== CACHE;
            })
            .map(function (k) {
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
  const req = e.request;
  if (req.method !== "GET") return;

  /* Anything that is not the page keeps the old behaviour: network first,
     stored copy if the network is slow or gone. */
  if (!isPage(req)) {
    e.respondWith(
      fetchWithTimeout(req)
        .then(function (res) {
          if (res && res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then(function (c) {
              c.put(req, copy);
            });
          }
          return res;
        })
        .catch(function (err) {
          return caches.match(req, { ignoreSearch: true }).then(function (hit) {
            if (hit) return hit;
            throw err;
          });
        })
    );
    return;
  }

  /* Keep the worker alive until the background refresh is stored. Registered
     now, settled later, so it holds on every browser. Every path settles it. */
  let settle;
  e.waitUntil(
    new Promise(function (r) {
      settle = r;
    })
  );

  e.respondWith(
    caches.match(req, { ignoreSearch: true }).then(
      function (hit) {
        if (hit) {
          /* Open instantly from the stored page. Revalidate rather than
             re-download: when nothing has been deployed the server answers
             "not modified" and almost nothing crosses the air. */
          settle(
            fetch(req.url, { cache: "no-cache", credentials: "same-origin" })
              .then(function (res) {
                if (res && res.ok && !res.redirected) return keep(req, res);
              })
              .catch(function () {})
          );
          return hit;
        }
        /* First launch: nothing stored, so the network is all there is. */
        return fetch(req).then(
          function (res) {
            settle(res && res.ok ? keep(req, res.clone()).catch(function () {}) : null);
            return res;
          },
          function (err) {
            settle(null);
            throw err;
          }
        );
      },
      function (err) {
        settle(null);
        return fetch(req);
      }
    )
  );
});
