#!/usr/bin/env python3
"""Behaviour regression checks for the Iron Log build.

smoke.py proves the app boots. This proves the things people actually do still
work: logging sets, ghost values, drop sets, menus, day swipe, search, themes
and the custom colours, the session sheet, and the wording of counts.

It runs against the built-in sample program with the clock pinned to
Wed 4 Nov 2026 (week 2 of 8, Tom Platz Leg Day), so results don't depend on
the day CI happens to run.

    python3 tools/regress.py http://localhost:8000/WorkoutApp.html

smoke.py calls run() after its boot check; any failure stops the deploy.
"""

import json
import re
import sys

CLOCK = """(() => { const _D = Date; const OFF = new _D('2026-11-04T10:00:00').getTime() - _D.now();
  class D extends _D { constructor(...a) { if (a.length === 0) super(_D.now() + OFF); else super(...a); }
    static now() { return _D.now() + OFF; } }
  window.Date = D; })();"""

SWIPE = """(dx) => { const h = document.querySelector('.dayhead'); const r = h.getBoundingClientRect();
  const x0 = r.left + r.width / 2, y0 = r.top + 40;
  const mk = (x, y) => new Touch({identifier: 1, target: h, clientX: x, clientY: y});
  h.dispatchEvent(new TouchEvent('touchstart', {touches: [mk(x0, y0)], changedTouches: [mk(x0, y0)], bubbles: true}));
  h.dispatchEvent(new TouchEvent('touchend', {touches: [], changedTouches: [mk(x0 + dx, y0)], bubbles: true})); }"""


class Checks:
    def __init__(self):
        self.failed, self.passed = [], 0

    def ok(self, cond, what):
        if cond:
            self.passed += 1
        else:
            self.failed.append(what)


def fresh(browser, url, touch=False):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=touch)
    pg = ctx.new_page()
    pg.add_init_script(CLOCK)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("dialog", lambda d: d.dismiss())
    pg.goto(url, wait_until="load")
    pg.wait_for_timeout(900)
    pg.evaluate("setSetting({autoRest:false}); render()")
    return ctx, pg, errs


def css(pg, name):
    return pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('%s').trim()" % name).upper()


def open_card(pg, i):
    pg.locator(".card").nth(i).locator(".card-top").click()
    pg.wait_for_timeout(120)
    return pg.locator(".card:has(.detail)")


def log_set(pg, card, i, w=None, r=None):
    if w is not None:
        card.locator('input[data-in=w][data-i="%d"]' % i).fill(w)
        card.locator('input[data-in=r][data-i="%d"]' % i).fill(r)
        card.locator('input[data-in=r][data-i="%d"]' % i).press("Tab")
    pg.locator(".card:has(.detail) .setrow .disc").nth(i).click()
    pg.wait_for_timeout(100)


def train_checks(browser, url, c):
    ctx, pg, errs = fresh(browser, url)
    c.ok(pg.locator(".dayhead .eyebrow").inner_text().upper().startswith("TODAY"), "opens on today")
    c.ok(pg.locator(".upnext").count() == 0, "no Up next banner")
    c.ok(pg.locator(".nag").count() == 0, "backup reminder is off the Train screen")
    c.ok(pg.locator(".dhside .ring").count() == 1 and pg.locator(".dhside .dmore").count() == 1, "ring + day menu in the day card")
    c.ok(pg.locator(".card").nth(0).locator(".discs").is_visible() is False, "collapsed lifts are summary pills")
    card = open_card(pg, 0)
    c.ok(pg.locator(".card:has(.detail) .setrow .disc").count() == 6, "each set row has its disc")
    log_set(pg, card, 0, "100", "8")
    c.ok("on" in pg.locator(".card:has(.detail) .setrow .disc").nth(0).get_attribute("class"), "row disc logs a set")
    d2 = pg.locator(".card:has(.detail) .setrow .disc").nth(1)
    c.ok(d2.get_attribute("data-sw") == "100", "next set carries the ghost value")
    d2.click(); pg.wait_for_timeout(100)
    c.ok(pg.locator('.card:has(.detail) input[data-in=w][data-i="1"]').input_value() == "100", "ghost tap writes the weight")
    pg.locator(".card:has(.detail) .setrow .disc").nth(1).click(); pg.wait_for_timeout(100)
    c.ok("on" not in pg.locator(".card:has(.detail) .setrow .disc").nth(1).get_attribute("class"), "untick clears a set")
    pg.locator('.card:has(.detail) [data-act=drop-add][data-i="2"]').click(); pg.wait_for_timeout(100)
    c.ok(pg.locator(".card:has(.detail) .setrow.drop").count() >= 1, "drop set adds")
    for i in range(1, 6):
        if "on" not in pg.locator(".card:has(.detail) .setrow .disc").nth(i).get_attribute("class"):
            log_set(pg, card, i)
    c.ok(pg.locator(".ring b").inner_text() == "1/9", "ring counts finished lifts")
    pg.locator(".card:has(.detail) .card-top").click(); pg.wait_for_timeout(100)
    c.ok(pg.locator(".card").nth(0).locator(".meta").inner_text().startswith("6 of 6 sets"), "done pill reads 6 of 6 sets")
    pg.click("[data-act=daymenu]"); pg.wait_for_timeout(100)
    c.ok(pg.locator(".dmenu [data-act=reorder-on]").count() == 1, "day menu opens")
    pg.click(".dmenu [data-act=clear-day]"); pg.wait_for_timeout(200)
    c.ok(pg.evaluate("dayProgress(currentDay()).done") == 6, "dismissed clear keeps the log")
    pg.reload(); pg.wait_for_timeout(900)
    c.ok(pg.evaluate("dayProgress(currentDay()).done") == 6, "log survives a reload")
    # finish -> session sheet -> wording
    pg.locator("[data-act=finish]").first.click(); pg.wait_for_timeout(200)
    pg.locator("[data-act=log-session]").click(); pg.wait_for_timeout(200)
    pg.click(".dock button >> nth=2"); pg.wait_for_timeout(150)
    pg.click(".tile[data-p=calendar]"); pg.wait_for_timeout(200)
    pg.click("[data-act=sess-open]"); pg.wait_for_timeout(250)
    c.ok(pg.locator(".ssex").count() == 1 and pg.locator(".ssrow.on").count() == 6, "session sheet lists the logged sets")
    whole = pg.evaluate("document.body.innerText")
    c.ok(not re.search(r"\b1 (sets|days|weeks|lifts|exercises)\b", whole), "no '1 sets' style wording")
    c.ok(errs == [], "no page errors on Train (%s)" % "; ".join(errs[:2]))
    ctx.close()


def swipe_checks(browser, url, c):
    ctx, pg, errs = fresh(browser, url, touch=True)
    eyebrow = lambda: pg.locator(".dayhead .eyebrow").inner_text().upper()
    pg.evaluate(SWIPE, -120); pg.wait_for_timeout(250)
    c.ok("THU" in eyebrow(), "swipe left goes to the next day")
    pg.evaluate(SWIPE, 120); pg.wait_for_timeout(250)
    c.ok(eyebrow().startswith("TODAY"), "swipe right comes back")
    pg.evaluate(SWIPE, 30); pg.wait_for_timeout(200)
    c.ok(eyebrow().startswith("TODAY"), "a short drag is ignored")
    for _ in range(5):
        pg.evaluate(SWIPE, -120); pg.wait_for_timeout(120)
    c.ok("MON" in eyebrow() and "NOV 9" in pg.locator(".wknav .lbl").inner_text().upper(), "swiping past Sunday rolls to next week")
    c.ok(errs == [], "no page errors while swiping")
    ctx.close()


def library_and_theme_checks(browser, url, c):
    ctx, pg, errs = fresh(browser, url)
    c.ok(css(pg, "--brass") == "#F0B43C" and css(pg, "--ink") == "#0A0A0A", "Ember on black by default")
    c.ok(pg.evaluate("document.fonts.check('800 20px \"Big Shoulders Display\"')"), "embedded display font loads")
    pg.click(".dock button >> nth=0"); pg.wait_for_timeout(250)
    pg.locator("#libq").fill("zzzz"); pg.locator("#libq").dispatch_event("input")
    c.ok(pg.locator("#libnone").is_visible(), "program search shows no-match")
    pg.locator("#libq").fill(""); pg.locator("#libq").dispatch_event("input")
    pg.click("[data-act=pmenu]"); pg.wait_for_timeout(100)
    pg.click(".pmenu [data-act=edit-prog]"); pg.wait_for_timeout(250)
    c.ok(pg.locator("textarea").count() > 0, "program menu Edit opens the editor")
    keys = pg.evaluate("Object.keys(THEMES)")
    c.ok(len(keys) == 10, "ten themes")
    for k in keys:
        pg.evaluate("setSetting({theme:'%s', accent:null, pop:null}); applyTheme()" % k)
        light = k in ("marshmallow", "daylight")
        c.ok(css(pg, "--ink") == ("#FFFFFF" if light else "#0A0A0A"), "%s background" % k)
        for fg in ("--chalk", "--mute", "--faint", "--brass", "--pop"):
            r = pg.evaluate("contrastOf(getComputedStyle(document.documentElement).getPropertyValue('%s').trim(), THEMES['%s'].panel)" % (fg, k))
            c.ok(r >= 4.5, "%s %s contrast %.2f" % (k, fg, r))
    pg.evaluate("setSetting({theme:'ember', accent:'#202060', pop:'#101010'}); applyTheme()")
    a = pg.evaluate("contrastOf(getComputedStyle(document.documentElement).getPropertyValue('--brass').trim(), THEMES.ember.panel)")
    p = pg.evaluate("contrastOf(getComputedStyle(document.documentElement).getPropertyValue('--pop').trim(), THEMES.ember.panel)")
    c.ok(a >= 4.5 and p >= 4.5, "unreadable custom colours are nudged readable")
    pg.evaluate("setSetting({accent:null, pop:null}); applyTheme()")
    c.ok(pg.evaluate("[plu(1,'set'),plu(2,'set'),plu(1,'day')].join('|')") == "1 set|2 sets|1 day", "count wording helper")
    c.ok(errs == [], "no page errors in Programs/Style")
    ctx.close()


def pb_moment_checks(browser, url, c):
    ctx, pg, errs = fresh(browser, url)
    # last week: Back Squat 100 x 8, so there is something on record to beat
    card = open_card(pg, 0)
    log_set(pg, card, 0, "100", "8")
    pg.evaluate("""(() => { const cur = wkNow(); const d = new Date(cur + 'T00:00:00'); d.setDate(d.getDate() - 7);
      S.log.weeks[ymd(d)] = S.log.weeks[cur]; delete S.log.weeks[cur]; S.pbFlash = null; persist(); render(); })()""")
    pg.wait_for_timeout(150)
    card = pg.locator(".card:has(.detail)")
    if not card.count():
        card = open_card(pg, 0)
    log_set(pg, card, 0, "105", "8")
    c.ok(pg.locator(".setrow.pbflash").count() == 1 and pg.locator(".pbnew").count() == 1, "beating last week fires the PB moment")
    pg.wait_for_timeout(2600)
    c.ok(pg.locator(".pbnew").count() == 0 and pg.locator(".setrow.pbflash").count() == 0, "PB moment clears itself")
    log_set(pg, card, 1, "100", "8")
    c.ok(pg.locator(".pbnew").count() == 0, "a set below today's best stays quiet")
    log_set(pg, card, 2, "105", "9")
    c.ok(pg.locator(".pbnew").count() == 1, "more reps at the top weight fires again")
    pg.wait_for_timeout(2600)
    card.locator('input[data-in=w][data-i="3"]').fill("110")
    card.locator('input[data-in=r][data-i="3"]').fill("5")
    card.locator('input[data-in=r][data-i="3"]').press("Tab")
    pg.wait_for_timeout(1100)  # auto-tick waits 0.7 s after typing stops
    c.ok(pg.locator(".pbnew").count() == 1, "auto-tick also fires the PB moment")
    # typed numbers win over the ghost when the disc is tapped straight away
    pg.wait_for_timeout(2600)
    card.locator('input[data-in=w][data-i="4"]').fill("97.5")
    card.locator('input[data-in=r][data-i="4"]').fill("7")
    pg.locator(".card:has(.detail) .setrow .disc").nth(4).click(); pg.wait_for_timeout(150)
    got = pg.evaluate("(() => { const e = entriesFor(currentDay().items.find(x => x.kind === 'ex').key)[4] || {}; return [e.w, e.r, !!e.d]; })()")
    c.ok(got == ["97.5", "7", True], "a typed set is logged as typed, not as the ghost (%s)" % got)
    c.ok(errs == [], "no page errors around PBs")
    ctx.close()


def remove_and_grab_checks(browser, url, c):
    # Remove for today on a program lift, then Put back
    ctx, pg, errs = fresh(browser, url)
    k = pg.evaluate("currentDay().items.filter(x => x.kind === 'ex')[1].key")
    pg.evaluate("S.openEx = %s; render()" % json.dumps(k))
    pg.locator('[data-act=ex-remove][data-key="%s"]' % k).click(); pg.wait_for_timeout(150)
    c.ok(pg.locator('.card-top[data-key="%s"]' % k).count() == 0, "Remove hides the lift for today")
    c.ok(pg.locator('[data-act=ex-restore][data-key="%s"]' % k).count() == 1, "Removed today list offers Put back")
    pg.locator('[data-act=ex-restore][data-key="%s"]' % k).click(); pg.wait_for_timeout(150)
    c.ok(pg.locator('.card-top[data-key="%s"]' % k).count() == 1, "Put back restores the lift")
    c.ok(errs == [], "no page errors around Remove")
    ctx.close()
    # A grab-and-go done Monday and opened again Wednesday starts clean,
    # with Monday filed under its own run and still in history
    ctx, pg, errs = fresh(browser, url)
    pg.evaluate("""(() => { localStorage.setItem(KEY, JSON.stringify({
      programs: [{ id: 'pG', title: 'Back Pump', raw: 'Back Pump\\nPull Day\\nLat Pulldown - 3x10\\nCable Row - 3x12' }],
      activeId: 'pG',
      log: { weeks: { '2026-11-02': { 'pG:d0e0': { 0: { d: true, w: '70', r: '10' }, n: 'Lat Pulldown' } } },
             sessions: { '2026-11-02': { 'pG:d0': { at: '2026-11-02T18:00:00Z', d: '2026-11-02', sets: 1, volume: 700,
                                                     pn: 'Back Pump', dn: '', gg: 1 } } },
             ggRun: { pG: '2026-11-02' }, settings: { autoRest: false } } })); })()""")
    pg.goto(url, wait_until="load"); pg.wait_for_timeout(900)
    c.ok(pg.evaluate("dayProgress(currentDay()).done") == 0, "repeat grab-and-go starts clean on a new day")
    keys = pg.evaluate("Object.keys(S.log.sessions['2026-11-02'] || {})")
    c.ok(any(":run20261102:" in x for x in keys), "earlier grab-and-go session filed under its own day")
    c.ok(pg.evaluate("(historyIndex()[nn('Lat Pulldown')] || []).length") == 1, "earlier run still counts as history")
    c.ok(errs == [], "no page errors around grab-and-go runs")
    ctx.close()


def rest_day_checks(browser, url, c):
    # a numbered program anchored on a Saturday has a rest slot on Friday;
    # its next session is next week's Day 1
    ctx, pg, errs = fresh(browser, url)
    pg.evaluate("""(() => { localStorage.setItem(KEY, JSON.stringify({
      programs: [{ id: 'pS', title: 'Six', start: '2026-10-24',
        raw: 'Six\\nDay 1 - Chest\\nBench - 4x8\\nDay 2 - Back\\nRow - 4x8\\nDay 3 - Legs\\nSquat - 4x6\\nDay 4 - Arms\\nCurl - 3x12\\nDay 5 - Shoulders\\nPress - 4x8\\nDay 6 - Full\\nDeadlift - 3x5' }],
      activeId: 'pS', log: { weeks: {}, sessions: {}, settings: { autoRest: false } } })); })()""")
    pg.goto(url, wait_until="load"); pg.wait_for_timeout(900)
    pg.locator(".pill").nth(6).click(); pg.wait_for_timeout(200)
    c.ok(pg.locator(".dayhead h1").inner_text().upper() == "REST", "rest slot shows the REST card")
    c.ok("rest day" not in pg.locator(".list").inner_text().lower(), "no duplicate rest-day line under the card")
    c.ok(pg.locator(".nextses b").inner_text().upper() == "CHEST", "next session is next week's first day")
    pg.click(".nextses"); pg.wait_for_timeout(200)
    c.ok(pg.evaluate("S.weekOff") == 1 and pg.locator(".dayhead h1").inner_text().upper() == "CHEST", "next-session strip opens it")
    c.ok(errs == [], "no page errors on rest days")
    ctx.close()


def run(url):
    from playwright.sync_api import sync_playwright

    c = Checks()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for fn in (train_checks, swipe_checks, pb_moment_checks, remove_and_grab_checks, rest_day_checks, library_and_theme_checks):
            try:
                fn(browser, url, c)
            except Exception as e:  # a crashed check is a failed check
                c.failed.append("%s crashed: %s" % (fn.__name__, str(e).splitlines()[0][:200]))
        browser.close()
    return c


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: regress.py <url>")
    res = run(sys.argv[1])
    print("%d passed, %d failed" % (res.passed, len(res.failed)))
    for f in res.failed:
        print("  - " + f)
    sys.exit(1 if res.failed else 0)
