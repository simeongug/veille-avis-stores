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


def _google(app, lang, country, since, max_count=1500):
    """Les avis Google Play dépendent de la langue, pas du pays : un avis est le même quel que soit le pays
    interrogé. On interroge donc une fois par langue, et le « lieu » d'un avis Android est sa langue."""
    from google_play_scraper import Sort, reviews
    out, token = [], None
    while len(out) < max_count:
        batch, token = reviews(app["android_package"], lang=lang, country=country, sort=Sort.NEWEST,
                               count=100, continuation_token=token)
        if not batch:
            break
        oldest = None
        for e in batch:
            d = e["at"].replace(tzinfo=timezone.utc) if e["at"].tzinfo is None else e["at"]
            oldest = d if oldest is None or d < oldest else oldest
            out.append({
                "id": f"android:{e['reviewId']}",
                "app": app["name"], "store": "android", "country": f"lang:{lang}",
                "lang": lang, "rating": int(e["score"]), "title": "",
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
    langs = {}
    for m in cfg["markets"]:
        langs.setdefault(m["lang"], m["country"])
    for app in cfg["apps"]:
        if app.get("ios_id"):
            for m in cfg["markets"]:
                try:
                    rows = _apple(app, m["country"], since)
                    _note(f"App Store {m['country'].upper()}", rows)
                    fetched += rows
                except Exception as ex:  # noqa: BLE001
                    errors.append(f"App Store {m['country'].upper()} : {type(ex).__name__}")
        if app.get("android_package"):
            for lang, ctry in langs.items():
                try:
                    rows = _google(app, lang, ctry, since, max_count)
                    _note(f"Google Play ({lang})", rows)
                    fetched += rows
                except Exception as ex:  # noqa: BLE001
                    errors.append(f"Google Play ({lang}) : {type(ex).__name__}")
    return fetched, errors


def _play_page_score(package):
    """Note telle qu'affichée sur la fiche publique Google Play (ce que voit un visiteur), ou None si illisible."""
    import re
    try:
        html = requests.get("https://play.google.com/store/apps/details", headers=UA, timeout=30,
                            params={"id": package, "hl": "en", "gl": "es"}).text
        for rx in (r'aria-label="Rated ([0-9]+(?:\.[0-9]+)?) stars', r'"ratingValue"\s*:\s*"?([0-9]+(?:\.[0-9]+)?)'):
            m = re.search(rx, html)
            if m and 1 <= float(m.group(1)) <= 5:
                return float(m.group(1))
    except Exception as ex:  # noqa: BLE001
        print(f"Fiche publique Google Play illisible ({type(ex).__name__})")
    return None


def fetch_ratings(cfg):
    """Note moyenne globale par magasin (toutes les notes, pas seulement les avis commentés)."""
    agg = {}

    def add(store, avg, count):
        a = agg.setdefault(store, [0.0, 0])
        a[0] += avg * count
        a[1] += count

    for app in cfg["apps"]:
        if app.get("ios_id"):
            for m in cfg["markets"]:
                try:
                    r = requests.get("https://itunes.apple.com/lookup", headers=UA, timeout=30,
                                     params={"id": app["ios_id"], "country": m["country"]}).json()
                    res = (r.get("results") or [{}])[0]
                    if res.get("userRatingCount"):
                        add("ios", res["averageUserRating"], res["userRatingCount"])
                except Exception as ex:  # noqa: BLE001
                    print(f"Note globale App Store {m['country'].upper()} indisponible ({type(ex).__name__})")
        if app.get("android_package"):
            try:
                from google_play_scraper import app as gp_app
                d = gp_app(app["android_package"], lang=cfg["markets"][0]["lang"], country=cfg["markets"][0]["country"])
                shown = _play_page_score(app["android_package"])
                if shown is not None:
                    print(f"Google Play : note affichée sur la fiche publique {shown} (outil de collecte : {d.get('score')})")
                hist = d.get("histogram") or []
                if len(hist) == 5 and sum(hist) > 0:  # moyenne recalculée sur la répartition 1 à 5 étoiles
                    avg = sum((i + 1) * c for i, c in enumerate(hist)) / sum(hist)
                    print(f"Google Play : répartition {hist}, moyenne {avg:.2f} (score affiché {d.get('score')})")
                    if shown is not None and abs(shown - avg) > 0.3:  # on s'aligne sur ce que voit un visiteur de la fiche
                        avg = shown
                    add("android", avg, sum(hist))
                elif d.get("ratings"):
                    add("android", d["score"], d["ratings"])
            except Exception as ex:  # noqa: BLE001
                print(f"Note globale Google Play indisponible ({type(ex).__name__})")
    return {k: {"avg": v[0] / v[1], "count": v[1]} for k, v in agg.items() if v[1]}
