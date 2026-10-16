"""Collecte des avis publics : flux RSS d'Apple et Play Store (sans accès propriétaire)."""
import time
from datetime import datetime, timezone

import requests

UA = {"User-Agent": "Mozilla/5.0 (avis-watch)"}


def _apple(app, country, since, max_pages=10):
    out = []
    for page in range(1, max_pages + 1):
        url = (f"https://itunes.apple.com/{country}/rss/customerreviews/"
               f"page={page}/id={app['ios_id']}/sortby=mostrecent/json")
        r = requests.get(url, headers=UA, timeout=30)
        if r.status_code != 200:
            break
        try:
            feed = r.json().get("feed", {})
        except ValueError:
            break
        entries = feed.get("entry") or []
        if isinstance(entries, dict):
            entries = [entries]
        entries = [e for e in entries if "im:rating" in e]
        if not entries:
            break
        oldest = None
        for e in entries:
            d = datetime.fromisoformat(e["updated"]["label"]).astimezone(timezone.utc)
            oldest = d if oldest is None or d < oldest else oldest
            out.append({
                "id": f"ios:{country}:{e['id']['label']}",
                "app": app["name"], "store": "ios", "country": country, "lang": "",
                "rating": int(e["im:rating"]["label"]),
                "title": e.get("title", {}).get("label", ""),
                "text": e.get("content", {}).get("label", ""),
                "date": d.isoformat(), "version": e.get("im:version", {}).get("label", ""),
                "thumbs": int(e.get("im:voteSum", {}).get("label", 0) or 0),
            })
        if oldest < since:
            break
        time.sleep(0.4)
    return out


def _google(app, market, since, max_count=1500):
    from google_play_scraper import Sort, reviews
    out, token = [], None
    while len(out) < max_count:
        batch, token = reviews(app["android_package"], lang=market["lang"],
                               country=market["country"], sort=Sort.NEWEST,
                               count=100, continuation_token=token)
        if not batch:
            break
        oldest = None
        for e in batch:
            d = e["at"].replace(tzinfo=timezone.utc) if e["at"].tzinfo is None else e["at"]
            oldest = d if oldest is None or d < oldest else oldest
            out.append({
                "id": f"android:{market['country']}:{e['reviewId']}",
                "app": app["name"], "store": "android", "country": market["country"],
                "lang": market["lang"], "rating": int(e["score"]), "title": "",
                "text": e.get("content") or "", "date": d.astimezone(timezone.utc).isoformat(),
                "version": e.get("appVersion") or "", "thumbs": int(e.get("thumbsUpCount") or 0),
            })
        if oldest < since or token is None:
            break
        time.sleep(0.4)
    return out


def _note(label, rows):
    if rows:
        ds = sorted(r["date"] for r in rows)
        print(f"{label} : {len(rows)} avis, du {ds[0][:10]} au {ds[-1][:10]}")
    else:
        print(f"{label} : 0 avis")


def collect_all(cfg, since, max_count=1500):
    """Retourne (avis, erreurs). Une source en échec n'arrête pas les autres."""
    fetched, errors = [], []
    for app in cfg["apps"]:
        for m in cfg["markets"]:
            if app.get("ios_id"):
                try:
                    rows = _apple(app, m["country"], since)
                    _note(f"App Store {m['country'].upper()}", rows)
                    fetched += rows
                except Exception as ex:  # noqa: BLE001
                    errors.append(f"App Store {m['country'].upper()} : {type(ex).__name__}")
            if app.get("android_package"):
                try:
                    rows = _google(app, m, since, max_count)
                    _note(f"Google Play {m['country'].upper()}", rows)
                    fetched += rows
                except Exception as ex:  # noqa: BLE001
                    errors.append(f"Google Play {m['country'].upper()} : {type(ex).__name__}")
    return fetched, errors
