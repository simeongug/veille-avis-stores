"""Alertes sur seuil : volume, note, sujet, gravité. Basées sur les avis arrivés récemment."""
from collections import Counter
from datetime import datetime, timedelta

from . import store
from .render import STORES, country, e, fnum, h, p, page, quote
from .report import THEME_LABELS, _to_text, dt, focus, meta_of, text_of


def _where(rs):
    c = Counter(r["country"] for r in rs)
    f = focus(c, country)
    return f or ", ".join(f"{country(k)} {v}" for k, v in c.most_common(3))


def check(cfg, recs, now):
    a = cfg["alerts"]
    out = []
    win = now - timedelta(minutes=a["window_minutes"])
    long_win = now - timedelta(hours=a["rating_window_hours"])
    fresh = now - timedelta(hours=24)
    for app in cfg["apps"]:
        mine = [r for r in recs.values() if r["app"] == app["name"]]
        arrivals = [r for r in mine if dt(r["first_seen"]) >= win and dt(r["date"]) >= fresh]
        longer = [r for r in mine if dt(r["first_seen"]) >= long_win and dt(r["date"]) >= fresh]
        week = sum(1 for r in mine if now - timedelta(days=7) <= dt(r["date"]) < win)
        base = max(0.5, week / 168 * a["window_minutes"] / 60)
        negs = [r for r in arrivals if r["a"]["sentiment"] == "negative"]

        if len(arrivals) >= a["volume_min"] and len(arrivals) >= a["volume_factor"] * base:
            out.append({"key": f"{app['name']}:volume", "title": f"{len(arrivals)} nouveaux avis en {a['window_minutes']} min",
                        "lines": [f"{fnum(len(arrivals) / base)}× le rythme habituel (environ {fnum(base, 0)} par période).",
                                  f"Dont {len(negs)} négatifs. Pays : {_where(arrivals)}."],
                        "examples": sorted(negs, key=lambda r: -len(r.get("text", "")))[:3]})

        if len(longer) >= a["rating_min_reviews"]:
            avg = sum(r["rating"] for r in longer) / len(longer)
            if avg <= a["rating_below"]:
                out.append({"key": f"{app['name']}:rating", "title": f"Note récente à {fnum(avg)}/5",
                            "lines": [f"Moyenne de {len(longer)} avis des {a['rating_window_hours']} dernières heures.",
                                      f"Pays : {_where(longer)}."],
                            "examples": [r for r in longer if r["a"]["sentiment"] == "negative"][:3]})

        themes = Counter(r["a"]["theme"] for r in longer if r["a"]["sentiment"] == "negative")
        for theme, n in themes.items():
            if n >= a["theme_min"]:
                rs = [r for r in longer if r["a"]["sentiment"] == "negative" and r["a"]["theme"] == theme]
                stores = Counter(r["store"] for r in rs)
                where = [x for x in (focus(stores, lambda s: STORES[s]), _where(rs)) if x]
                out.append({"key": f"{app['name']}:theme:{theme}",
                            "title": f"{THEME_LABELS[theme]} : {n} avis négatifs en {a['rating_window_hours']} h",
                            "lines": [" · ".join(where)], "examples": rs[:3]})

        crit = [r for r in longer if r["a"]["severity"] >= 3]
        if crit:
            out.append({"key": f"{app['name']}:critique", "title": f"{len(crit)} avis critique(s)",
                        "lines": ["Plantage total, connexion impossible, paiement ou données personnelles."],
                        "examples": crit[:3]})
    return out


def filter_cooldown(cfg, alerts, now):
    state = store.read_json(cfg, "alerts.json", {})
    keep = []
    for al in alerts:
        last = state.get(al["key"])
        if last and now - datetime.fromisoformat(last) < timedelta(minutes=cfg["alerts"]["cooldown_minutes"]):
            continue
        keep.append(al)
    return keep, state


def mark_sent(cfg, state, alerts, now):
    for al in alerts:
        state[al["key"]] = now.isoformat()
    store.write_json(cfg, "alerts.json", state)


def build(cfg, alerts, now, test=False):
    tz = __import__("zoneinfo").ZoneInfo(cfg["timezone"])
    # Plusieurs seuils franchis pour un même incident : un seul bloc, les autres seuils en lignes.
    blocks = [h(alerts[0]["title"])]
    for al in alerts[1:]:
        blocks.append(p("+ " + e(al["title"])))
    for al in alerts:
        blocks += [p(e(ln)) for ln in al["lines"] if ln]
    seen = set()
    for al in alerts:
        for r in al["examples"]:
            if r["id"] not in seen and len(seen) < 3:
                seen.add(r["id"])
                blocks.append(quote(text_of(r), meta_of(r)))
    prefix = "[TEST] " if test else ""
    extra = f" (+{len(alerts) - 1} seuil{'s' if len(alerts) > 2 else ''})" if len(alerts) > 1 else ""
    subject = f"{prefix}Alerte {cfg['name']} · {alerts[0]['title']}{extra}"
    html = page(f"Alerte · {cfg['name']}", f"{now.astimezone(tz):%d/%m/%Y à %H:%M}", blocks, accent="#B42318")
    return subject, html, _to_text(blocks)
