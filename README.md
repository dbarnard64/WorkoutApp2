# Iron Log

A single-file workout tracker. Paste a training program in as plain text and it becomes a day-by-day app with set tracking, weight logging, rest timer, history and a plate calculator.

**Live:** https://dbarnard64.github.io/WorkoutApp2/WorkoutApp.html

Open it in Safari, then Share → Add to Home Screen for a full-screen app icon. No account needed. Everything is stored in the browser on your own device, so each person who opens the link gets their own private copy.

---

## Adding a workout

Programs are added under **Programs → Paste another program**. The parser is deliberately forgiving, but it works best if you follow the shape below.

### Day headers

Each day goes on its own line. Anything after a dash becomes the day's title.

```
Monday - Upper Power (Chest Focus)
Tuesday - Back Thickness & Width
```

`Day 1`, `Day 2` etc. also work. The first three letters show on the day pill, the title shows as the heading.

### Exercises

Any of these formats are recognised:

| Written as | Result |
| --- | --- |
| Name, then sets, then reps on three separate lines | 4 sets of 8–10 (this is what pasting a table produces) |
| `Bench Press - 4x8` | 4 sets of 8 |
| `Bench Press: 3 sets of 12` | 3 sets of 12 |
| `Bench Press 4x8-10` | 4 sets of 8–10 |
| `4x8 Bench Press` | 4 sets of 8 |
| `Sled Push x 6 rounds` | 6 rounds |
| `Farmer carries` | one tickable item |

Reps can be a number (`8`), a range (`5-8`), or text like `20 steps`, `AMRAP`, `failure`.

### Section labels

A line ending in a colon, or beginning with Giant Set / Superset / Circuit / Finish / Warm-up, becomes a section label. Short one-word labels like `Triceps` work too.

If the label mentions rounds, the exercises beneath it inherit that many sets:

```
Giant Set 1 (4 rounds)
Incline Smith Press x12
Neutral Grip Pulldown x12
```

Both exercises get 4 sets.

### Week conditions

Put the condition in brackets after the exercise name. The bracket is stripped from the name and shown as a badge instead.

```
Deadlift (Weeks 1,3,5,7)
Rack Pull (Weeks 2,4,6,8)
```

Also understood: `(Weeks 1-4)`, `(odd weeks)`, `(even weeks)`.

Exercises that are not scheduled for the current program week are greyed out and excluded from the day's completion percentage and the finish-workout totals. They stay tappable in case you swap on the day.

### Notes

Lines ending in a full stop, or longer than eight words, render as grey note text rather than as exercises:

```
Keep rest periods to 45-60 seconds.
```

Headings containing words like *principles*, *progression*, *nutrition*, *deload* or *recovery* are pulled out of the day list into the **Notes** tab, along with everything under them.

---

## Program weeks

Set **Week 1 starts** to the date you began. Pick any day in that week; it snaps to that Monday. The header then shows `WEEK 4 / 8`, which is what drives the week-condition badges above.

Program length is read from any "8 weeks" in the text, or from the highest week number used in a condition. Past the end it cycles and shows `R2`, `R3` and so on.

---

## Tips

- The paste screen shows a live count of days and exercises per day before you save. If a number looks wrong, something in the text needs a tweak — usually a day header that is not on its own line.
- The title is the first short line before the first day header.
- Nothing is destructive: tap the pencil on any program to edit its raw text and re-parse.
- To hand a program to someone else, tap the copy icon next to it in the Programs tab and send them the text to paste into their own copy.

---

## Updating the app

Ask Claude for the change you want and it deploys — from a phone is fine. Logged sets live in each phone's browser rather than in the file, so updates never wipe your history.

**Do not upload a new `WorkoutApp.html` over the old one.** That file is now built, not edited. The source of truth is `src/chunks/`, and the next deploy would overwrite anything pasted over the top of it.

### How a deploy works

The app is split into ~24 KB line-aligned chunks under `src/chunks/`, with `manifest.json` recording the part count, byte length and sha256 of the finished file. A change means pushing only the chunks it touches, not the whole 200 KB.

On every push to `main`, `.github/workflows/deploy.yml`:

1. reassembles `WorkoutApp.html` from the chunks
2. checks the sha256 against the manifest — did it build what was intended?
3. boots the result in headless Chromium — does what it built actually work?
4. only then commits the published file

Step 2 catches an incomplete or corrupted chunk push. Step 3 (`tools/smoke.py`) catches a build that assembles perfectly and then white-screens: it checks the app renders, parses a program, survives a reload, and keeps `</html>` within the last 200 bytes, which is the window `sw.js` uses to decide a downloaded page arrived whole.

Either check failing stops the run and leaves the live file untouched.

### If a deploy goes wrong anyway

The build being replaced is kept at **https://dbarnard64.github.io/WorkoutApp2/previous.html** — open that and carry on. Your logged sets are in the browser, not the file, so the old version sees all of them.

### Rebuilding the chunks

If the chunks ever get out of step with the published file, delete `src/chunks/manifest.json` and push. The workflow re-splits `WorkoutApp.html` into fresh chunks and commits them.
