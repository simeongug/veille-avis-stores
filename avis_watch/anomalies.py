"""Détection d'anomalies : écarts inhabituels du jour par rapport aux jours précédents, par plateforme."""
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .render import STORES, fnum


def _dt(iso):
    return datetime.fromisoformat(iso)


def _norm(text):
    return re.sub(r"\W+", " ", text.lower()).strip()


def version_focus(rs):
    """« version 9.3.9 (87 %) » si une version concentre l'essentiel des avis donnés."""
    vs = Counter(r["version"] for r in rs if r.get("version"))
    if len(rs) >= 5 and vs:
        v, c = vs.most_common(1)[0]
        if c / len(rs) >= 0.7:
            return f"version {v} ({round(100 * c / len(rs))} %)"
    return ""


def detect(cfg, recs, day, theme_labels):
    a = cfg["anomaly"]
    tz = ZoneInfo(cfg["timezone"])
    win = a["baseline_days"]
    by = defaultdict(list)
    for r in recs.values():
        by[_dt(r["date"]).astimezone(tz).date()].append(r)

    out = []
    for store in ("ios", "android"):
        cur = [r for r in by.get(day, []) if r["store"] == store]
        hist = [r for k in range(1, win + 1) for r in by.get(day - timedelta(days=k), []) if r["store"] == store]
        n = len(cur)
        base_n = len(hist) / win
        sig, kinds = [], []

        if n >= a["volume_min"] and n >= a["volume_factor"] * max(base_n, 1):
            habit = f"{fnum(base_n, 0)} par jour d'habitude" if base_n >= 1 else "moins de 1 par jour d'habitude"
            sig.append(f"{n} avis contre {habit} (×{round(n / max(base_n, 1))})")
            kinds.append("volume")
        elif base_n >= a["silence_base_min"] and n <= 0.2 * base_n:
            sig.append(f"seulement {n} avis contre {fnum(base_n, 0)} par jour d'habitude : silence inhabituel "
                       f"(ou collecte incomplète)")
            kinds.append("silence")

        if n >= a["min_reviews"]:
            avg = sum(r["rating"] for r in cur) / n
            bavg = (sum(r["rating"] for r in hist) / len(hist)) if len(hist) >= a["baseline_min_reviews"] else None
            if avg <= a["rating_low"] or (bavg is not None and bavg - avg >= a["rating_drop"]):
                sig.append(f"moyenne du jour {fnum(avg)}" + (f" contre {fnum(bavg)} d'habitude" if bavg else ""))
                kinds.append("note")
            neg = sum(r["rating"] <= 2 for r in cur) / n
            if neg >= a["neg_share"]:
                bneg = (sum(r["rating"] <= 2 for r in hist) / len(hist)) if len(hist) >= a["baseline_min_reviews"] else None
                sig.append(f"{round(neg * 100)} % d'avis à 1-2 étoiles" +
                           (f" contre {round(bneg * 100)} % d'habitude" if bneg is not None else ""))
                kinds.append("negatifs")

        negs = [r for r in cur if r["rating"] <= 2]
        if len(negs) >= 8:
            vs = Counter(r["version"] for r in negs if r.get("version"))
            if vs:
                v, c = vs.most_common(1)[0]
                share = c / len(negs)
                first = min(_dt(r["date"]) for r in recs.values() if r["store"] == store and r.get("version") == v)
                is_new = first.astimezone(tz).date() >= day - timedelta(days=3)
                hv = [r for r in hist if r.get("version")]
                base_share = (sum(r["version"] == v for r in hv) / len(hv)) if len(hv) >= 10 else None
                if share >= a["version_share"] and (is_new or (base_share is not None and share - base_share >= 0.2)):
                    sig.append(f"{round(share * 100)} % des avis négatifs viennent de la version {v}"
                               + (" (version récente, possible régression)" if is_new else ""))
                    kinds.append("version")

        if hist or cur:
            tc = Counter(r["a"]["theme"] for r in cur if r["a"]["sentiment"] == "negative" and r["a"]["theme"] != "autre")
            for theme, c in tc.most_common(3):
                b = sum(1 for r in hist if r["a"]["sentiment"] == "negative" and r["a"]["theme"] == theme) / win
                if c >= a["theme_min"] and c >= a["theme_factor"] * max(b, 0.5):
                    sig.append(f"{theme_labels[theme]} : {c} avis négatifs, {round(c / max(b, 0.5))} fois la normale")
                    kinds.append("sujet")

        rep = Counter(_norm(r.get("text", "")) for r in cur if len(r.get("text", "")) >= 25)
        for text, c in rep.most_common(1):
            if c >= 3:
                sig.append(f"{c} avis identiques mot pour mot (« {text[:60]}… »), possible campagne")
                kinds.append("repetes")

        if sig:
            strong = len(sig) >= 3 or ("volume" in kinds and ("note" in kinds or "negatifs" in kinds))
            out.append({"store": STORES[store], "level": "forte" if strong else "modérée",
                        "signals": sig, "kinds": kinds, "n": n})
    return out
