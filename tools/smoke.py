#!/usr/bin/env python3
"""Pre-publish smoke test for the Iron Log build.

The manifest hash proves the chunks assembled into the file we meant to ship.
It says nothing about whether that file works. This does: it boots the assembled
build in headless Chromium and refuses the deploy if the app does not come up.

    python3 tools/smoke.py WorkoutApp.html

Exit 0 = safe to publish. Any failure exits non-zero and the workflow stops
before the live file is touched.
"""

import http.server
import os
import socketserver
import sys
import threading

SW_TAIL_BUDGET = 200  # sw.js only caches a page whose </html> lands this near the end


def structural_checks(path):
    with open(path, "rb") as fh:
        data = fh.read()
    problems = []

    if not data.lstrip().startswith(b"<!DOCTYPE"):
        problems.append("does not start with <!DOCTYPE")

    close = data.rfind(b"</html>")
    if close < 0:
        problems.append("no closing </html>")
    else:
        tail = len(data) - close
        if tail > SW_TAIL_BUDGET:
            problems.append(
                "</html> is %d bytes from the end; sw.js only caches a page when it is "
                "within %d, so offline mode would silently stop working"
                % (tail, SW_TAIL_BUDGET)
            )

    opens = data.count(b"<script")
    closes = data.count(b"</script>")
    if opens != closes:
        problems.append("unbalanced script tags (%d open, %d close)" % (opens, closes))

    if len(data) < 50000:
        problems.append("suspiciously small (%d bytes)" % len(data))

    return problems


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve(root):
    """Serve the build's own directory so sw.js and rescue.html resolve as they
    do in production. Port 0 lets the OS pick a free one - a fixed port collides
    with a lingering socket from the previous run."""
    os.chdir(root)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", 0), QuietHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd.server_address[1]


def boot_check(filename, port):
    from playwright.sync_api import sync_playwright

    errors, failures = [], []
    url = "http://localhost:%d/%s" % (port, filename)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        # A phone is the only device this app ever runs on.
        page = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
        ).new_page()

        page.on("pageerror", lambda e: failures.append("uncaught: %s" % e))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        page.goto(url, wait_until="load")
        page.wait_for_timeout(1200)

        alive = page.evaluate("typeof appAlive !== 'undefined' && appAlive === true")
        if not alive:
            failures.append("app did not finish booting (appAlive never became true)")

        body = page.inner_text("body")
        if "Something broke" in body:
            failures.append("app booted into its ironFail error screen")

        if page.evaluate("!document.getElementById('app') || !document.getElementById('app').children.length"):
            failures.append("#app rendered nothing")

        # The parser is the heart of the app - a build that cannot read a program
        # is useless even if it paints a screen.
        parsed = page.evaluate(
            """(() => {
              try {
                const src = ["Test Block", "Monday - Upper", "Bench Press - 4x8", ""];
                const dp = parseProgram(src.join(String.fromCharCode(10)));
                return dp && dp.days && dp.days.length ? dp.days.length : 0;
              } catch (e) { return "threw: " + e.message; }
            })()"""
        )
        if parsed != 1:
            failures.append("parseProgram did not read a one-day program (got %r)" % parsed)

        # Second load exercises the migration and rehydration path, which is where
        # a bad build usually dies rather than on a clean first run.
        page.reload(wait_until="load")
        page.wait_for_timeout(1200)
        if not page.evaluate("typeof appAlive !== 'undefined' && appAlive === true"):
            failures.append("app failed to boot on reload with stored state")

        browser.close()

    return failures, errors


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: smoke.py <file>")
    target = sys.argv[1]
    root = os.path.dirname(os.path.abspath(target)) or "."
    filename = os.path.basename(target)

    problems = structural_checks(target)
    if problems:
        print("Structural checks failed:")
        for p in problems:
            print("  - " + p)
        sys.exit(1)
    print("Structural checks passed.")

    port = serve(root)
    failures, errors = boot_check(filename, port)

    for e in errors:
        print("  console error: " + e[:300])

    if failures:
        print("Smoke test FAILED - not publishing:")
        for f in failures:
            print("  - " + f[:500])
        sys.exit(1)

    print("Smoke test passed: app boots, renders, parses a program, and survives a reload.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
