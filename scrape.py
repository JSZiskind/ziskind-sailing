#!/usr/bin/env python3
"""
Scrape College Sailing TechScore and build data.json for the Ziskind Sailing dashboard.
Run by GitHub Actions on race weekends (and on demand). Local use: `python3 scrape.py`.

Source: https://scores.collegesailing.org  (ICSA official scoring, server-rendered HTML).
Writes data.json next to this script. Exits non-zero (without overwriting) if a core page fails,
so a bad run never clobbers good data.
"""
import re, sys, json, ssl, datetime, urllib.request

BASE = "https://scores.collegesailing.org"
UA = "ZiskindSailingDashboard/1.0 (+github.com/JSZiskind/ziskind-sailing)"

try:
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL = ssl.create_default_context()

SAILORS = {
    "zoey": {"slug": "zoey-ziskind", "first": "Zoey", "last": "Ziskind", "initials": "Z",
             "school": "Harvard University", "team": "Crimson", "team_full": "Harvard Crimson",
             "conf": "NEISA", "cls_color": "z", "school_slug": "harvard"},
    "crue": {"slug": "crue-ziskind", "first": "Crue", "last": "Ziskind", "initials": "C",
             "school": "Tufts University", "team": "Jumbos", "team_full": "Tufts Jumbos",
             "conf": "NEISA", "cls_color": "c", "school_slug": "tufts"},
}
TEAMS = {
    "harvard": {"slug": "harvard", "name": "Harvard Crimson", "short": "HAR", "cls_color": "z", "conf": "NEISA"},
    "tufts":   {"slug": "tufts",   "name": "Tufts Jumbos",    "short": "TUF", "cls_color": "c", "conf": "NEISA"},
}

try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Missing dependency: pip install beautifulsoup4")


def fetch(path):
    url = path if path.startswith("http") else BASE + path
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30, context=_SSL) as r:
        return r.read().decode("utf-8", "replace")


def soup_of(path):
    return BeautifulSoup(fetch(path), "html.parser")


def ordinal(n):
    if n is None:
        return ""
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1:'st',2:'nd',3:'rd'}.get(n % 10,'th')}"


def class_label(grad):
    """Senior/Junior/etc. from graduation year and the current academic fall year."""
    now = datetime.datetime.now()
    fall_year = now.year if now.month >= 8 else now.year - 1
    diff = grad - fall_year
    return {1: "Senior", 2: "Junior", 3: "Sophomore", 4: "Freshman"}.get(diff, "")


def parse_place(text):
    """'4/18 (A Div)' -> (4,18,'A'); '2/8' -> (2,8,None); 'N/A' -> (None,None,None);
    doubled '2/52/5' -> (2,5,None)."""
    text = (text or "").strip()
    if not text or text.upper() == "N/A":
        return (None, None, None)
    m = re.search(r"(\d+)\s*/\s*(\d+)", text)
    place = int(m.group(1)) if m else None
    fleet = int(m.group(2)) if m else None
    dm = re.search(r"\(([ABC])\s*Div\)", text)
    return (place, fleet, dm.group(1) if dm else None)


def data_tables(soup, header):
    """All tables whose first row matches `header`, paired with the preceding <h3> text."""
    out = []
    for t in soup.find_all("table"):
        rows = t.find_all("tr")
        if not rows:
            continue
        cells = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
        if cells[:len(header)] == header:
            h3 = t.find_previous("h3")
            out.append((h3.get_text(strip=True) if h3 else "", t))
    return out


# ---------- sailor ----------
def scrape_sailor(key):
    cfg = SAILORS[key]
    s = soup_of(f"/sailors/{cfg['slug']}/")
    body = s.get_text(" ", strip=True)
    gm = re.search(r"Graduation Year\s*(\d{4})", body)
    grad = int(gm.group(1)) if gm else None

    HEAD = ["Name", "Host", "Date", "Position", "Place finish"]
    live = None
    seasons = []
    for label, table in data_tables(s, HEAD):
        rows = table.find_all("tr")[1:]
        parsed = []
        for tr in rows:
            td = tr.find_all("td")
            if len(td) < 5:
                continue
            a = td[0].find("a")
            slug = a["href"] if a else None
            name = td[0].get_text(strip=True)
            host = td[1].get_text(strip=True)
            date = td[2].get_text(strip=True)
            pos = td[3].get_text(strip=True)
            place, fleet, div = parse_place(td[4].get_text(strip=True))
            parsed.append({"name": name, "host": host, "date": date, "position": pos,
                           "place": place, "fleet": fleet, "div": div, "_slug": slug})
        if label.lower().startswith("sailing now"):
            if parsed:
                live = build_live(cfg, parsed[0])
        elif label.lower().startswith("season history for"):
            season = label.split("for", 1)[1].strip()
            seasons.append({"label": season,
                            "races": [{k: r[k] for k in ("name", "host", "date", "position", "place", "fleet", "div")} for r in parsed]})

    return {
        "first": cfg["first"], "last": cfg["last"], "initials": cfg["initials"],
        "cls": grad, "year": class_label(grad) if grad else "",
        "school": cfg["school"], "team": cfg["team"], "conf": cfg["conf"],
        "cls_color": cfg["cls_color"], "url": f"{BASE}/sailors/{cfg['slug']}/",
        "live": live, "seasons": seasons,
    }


def build_live(cfg, row):
    live = {"reg": row["name"], "host": row["host"], "pos": row["position"],
            "place": row["place"], "fleet": row["fleet"], "div": row["div"],
            "team": cfg["team_full"], "teamPlace": None, "teamField": None,
            "note": "", "url": (BASE + row["_slug"]) if row["_slug"] else BASE}
    if row["_slug"]:
        try:
            rank, field, note = regatta_standing(row["_slug"], cfg["school_slug"])
            live["teamPlace"], live["teamField"], live["note"] = rank, field, note
        except Exception as e:
            print(f"  (live standing fetch failed for {row['_slug']}: {e})", file=sys.stderr)
    return live


def regatta_standing(reg_path, school_slug):
    """Return (rank, field, note) for a school in a regatta's score summary."""
    s = soup_of(reg_path)
    table = s.find("table", class_="results")
    rank, field = None, 0
    if table:
        for tr in table.find_all("tr"):
            link = tr.find("a", href=re.compile(rf"/schools/{school_slug}/"))
            tds = tr.find_all("td")
            if not tds:
                continue
            # a data row: has a schoolname link somewhere
            if tr.find(class_="schoolname") or link:
                field += 1
            if link:
                nums = [td.get_text(strip=True) for td in tds if td.get_text(strip=True).isdigit()]
                rank = int(nums[0]) if nums else None
    # note: last sentence of the Summary/Report text
    note = ""
    h = s.find(lambda tag: tag.name in ("h2", "h3") and tag.get_text(strip=True).lower() in ("summary", "report"))
    if h:
        txt = ""
        for sib in h.find_all_next(string=True):
            txt += " " + sib.strip()
            if len(txt) > 600:
                break
        sents = [x.strip() for x in re.split(r"(?<=[.!])\s+", txt) if 15 < len(x.strip()) < 160]
        if sents:
            note = sents[-1]
    return rank, field, note


# ---------- team ----------
def scrape_team(key):
    cfg = TEAMS[key]
    s = soup_of(f"/schools/{cfg['slug']}/")
    body = s.get_text(" ", strip=True)
    nm = re.search(r"Number of Regattas\s*(\d+)", body)
    regattas = int(nm.group(1)) if nm else None

    now, season = [], []
    for label, table in data_tables_by_contains(s, "Place(s)"):
        header = [c.get_text(strip=True) for c in table.find_all("tr")[0].find_all(["th", "td"])]
        rows = table.find_all("tr")[1:]
        if "Last race" in header:  # Sailing now
            for tr in rows:
                td = tr.find_all("td")
                if len(td) < 6:
                    continue
                a = td[0].find("a")
                places = td[5].get_text(strip=True)
                pm = re.search(r"(\d+)", places)
                fm = re.search(r"/\s*(\d+)", places)
                status = td[4].get_text(strip=True)
                now.append({"reg": td[0].get_text(strip=True), "host": td[1].get_text(strip=True),
                            "status": status, "live": status.lower() != "finished",
                            "place": ordinal(int(pm.group(1))) if pm else places,
                            "field": int(fm.group(1)) if fm else None,
                            "link": (BASE + a["href"]) if a else BASE})
        elif "Status" in header:  # Season history (current season)
            for tr in rows:
                td = tr.find_all("td")
                if len(td) < 7:
                    continue
                places = td[6].get_text(strip=True)
                pm = re.search(r"(\d+)", places)
                fm = re.search(r"/\s*(\d+)", places)
                season.append([td[0].get_text(strip=True), td[1].get_text(strip=True),
                               td[4].get_text(strip=True),
                               pm.group(1) if pm else places, fm.group(1) if fm else ""])

    return {"name": cfg["name"], "short": cfg["short"], "cls_color": cfg["cls_color"],
            "conf": cfg["conf"], "regattas": regattas, "url": f"{BASE}/schools/{cfg['slug']}/",
            "now": now, "season": season[:16]}


def data_tables_by_contains(soup, header_token):
    out = []
    for t in soup.find_all("table"):
        rows = t.find_all("tr")
        if not rows:
            continue
        cells = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
        if any(header_token == c for c in cells):
            h3 = t.find_previous("h3")
            out.append((h3.get_text(strip=True) if h3 else "", t))
    return out


def eastern_now_iso():
    # EDT (-04:00) Mar-Nov, EST (-05:00) otherwise — good enough for a display stamp.
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    edt = 3 <= now.month <= 11
    off = -4 if edt else -5
    local = now + datetime.timedelta(hours=off)
    return local.strftime("%Y-%m-%dT%H:%M:%S") + (f"{off:+03d}:00")


def main():
    data = {"updated": eastern_now_iso()}
    # core pages first — if any raises, we exit without writing
    data["zoey"] = scrape_sailor("zoey")
    data["crue"] = scrape_sailor("crue")
    data["teams"] = {"harvard": scrape_team("harvard"), "tufts": scrape_team("tufts")}

    # sanity: each sailor must have at least one season with races
    for k in ("zoey", "crue"):
        if not any(s["races"] for s in data[k]["seasons"]):
            sys.exit(f"Refusing to write: no race history parsed for {k}")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    z, c = data["zoey"], data["crue"]
    print(f"Wrote data.json @ {data['updated']}")
    print(f"  Zoey: {z['year']} '{str(z['cls'])[2:]}, {sum(len(s['races']) for s in z['seasons'])} races, live={bool(z['live'])}")
    print(f"  Crue: {c['year']} '{str(c['cls'])[2:]}, {sum(len(s['races']) for s in c['seasons'])} races, live={bool(c['live'])}")
    print(f"  Teams: Harvard now={len(data['teams']['harvard']['now'])} / Tufts now={len(data['teams']['tufts']['now'])}")


if __name__ == "__main__":
    main()
