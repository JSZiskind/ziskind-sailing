# Ziskind Sailing dashboard

A live, self-updating dashboard tracking college-sailing results for **Zoey Ziskind**
(Harvard '27) and **Crue Ziskind** (Tufts '29), plus the Harvard Crimson and Tufts
Jumbos teams. Data comes from the ICSA's official scoring site, **TechScore**
(scores.collegesailing.org).

**Live page:** https://jsziskind.github.io/ziskind-sailing/

## How it works

- `index.html` — the dashboard. Static; it fetches `./data.json` at load and renders from it. **Never hand-edit data into this file.**
- `data.json` — all the results. The only file that changes when results update.
- `scrape.py` — fetches the four TechScore pages (two sailors + two schools) plus any live regatta pages, and rebuilds `data.json`. Preserves full career history (the sailor pages carry every season).
- `.github/workflows/refresh.yml` — a GitHub Action that runs `scrape.py` on **race weekends** (Sat & Sun, roughly every 2 hours, 9am–7pm ET) and commits `data.json` if anything changed. GitHub Pages serves the repo, so a commit goes live immediately.

### Run it yourself

- On demand: GitHub → **Actions → Refresh dashboard data → Run workflow**.
- Locally: `pip install beautifulsoup4 certifi && python3 scrape.py` (writes `data.json`).

### Change who/what is tracked

Edit the `SAILORS` and `TEAMS` config dicts at the top of `scrape.py`.

## Data source

College Sailing TechScore. Each sailor page shows that sailor's complete multi-year
history; each school page shows the team's current-season results and anything racing
now; each regatta page carries the team standings used on the live cards.
