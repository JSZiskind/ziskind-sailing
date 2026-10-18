# Ziskind Sailing dashboard

A shareable dashboard tracking college-sailing results for **Zoey Ziskind** (Harvard '27)
and **Crue Ziskind** (Tufts '29), plus the Harvard Crimson and Tufts Jumbos teams.
Data comes from the ICSA's official scoring site, **TechScore** (scores.collegesailing.org).

- `index.html` — the dashboard page. Static; it fetches `./data.json` at load and renders everything from it. **Do not hand-edit the data into this file.**
- `data.json` — all the results. This is the only file that changes when results update.

Published as a Claude Artifact: **https://claude.ai/artifact/2z4DqjGsHmt63cZdNgpXoG**

## Refreshing the results (what the race-weekend routine does)

Goal: regenerate `data.json` from TechScore and re-publish it to the artifact so the live
page shows the latest standings. The page itself (`index.html`) rarely changes.

1. **Fetch the four core TechScore pages** (server-side `WebFetch` works — no CORS limit):
   - Zoey: `https://scores.collegesailing.org/sailors/zoey-ziskind/`
   - Crue: `https://scores.collegesailing.org/sailors/crue-ziskind/`
   - Harvard: `https://scores.collegesailing.org/schools/harvard/`
   - Tufts: `https://scores.collegesailing.org/schools/tufts/`
2. For **each sailor**: the page lists a "Sailing now" section (0+ rows) and "Season history for &lt;Season&gt;" tables. Each result row is `Name | Host | Date | Position | Place finish`. Place finish looks like `4/18 (A Div)` (fleet race) or `2/8` (team race) or `N/A` (Reserve).
3. For **each team**: the school page has a "Sailing now" table and a "Season history for Fall 2026" table with a `Place(s)` column like `7/18` or `2,8/15`.
4. For any **live regatta** (a "Sailing now" row), also fetch that regatta page (linked from the school page, e.g. `/f26/<slug>/`) to read the team's overall standing and a one-line note from the Summary/Report.
5. **Rewrite `data.json`** to match the schema below. Keep ALL historical seasons already in the file and only add/update the current season and live entries — never drop history. Set `updated` to the current time in US Eastern, RFC3339 with offset, e.g. `2026-10-25T14:10:00-04:00`.
6. **Validate**: `python3 -c "import json; json.load(open('data.json'))"` must succeed.
7. **Re-publish** `data.json` to the artifact URL above (page unchanged), then **commit** the updated `data.json` back to this repo.

### `data.json` schema

```
{
  "updated": "<RFC3339 Eastern timestamp>",
  "zoey": <sailor>, "crue": <sailor>,
  "teams": { "harvard": <team>, "tufts": <team> }
}

sailor = {
  first, last, initials, cls (grad year int), year ("Junior"/"Sophomore"/…),
  school, team, conf, cls_color ("z" for Zoey/Harvard, "c" for Crue/Tufts), url,
  live: null  OR  { reg, host, pos, place (int), fleet (int), div ("A"/"B"/"C"),
                    team, teamPlace (int), teamField (int), note, url },
  seasons: [ { label: "Fall 2026", races: [ race, … ] }, … ]  // newest season first
}
race = { name, host, date ("Oct 10"), position ("Skipper"/"Crew"/"Reserve"),
         place (int|null — null for Reserve/DNS), fleet (int|null), div ("A"/"B"/"C"|null) }
         // div is null for team races and combined-division regattas
         // within a season, races are listed newest first

team = {
  name, short (3-letter code), cls_color, conf, regattas (int), url,
  now: [ { reg, host, status ("Race 10B"/"Finals Sunday"/"Finished"), live (bool),
           place ("7th"), field (int), link } ],   // may be empty
  season: [ [ name, host, date, place (string), field (string) ], … ]  // newest first; up to ~14 rows
}
```

Keep the `cls_color` values exactly (`"z"` / `"c"`) — the page colors everything from them.
