"""Rapport quotidien : les chiffres sont calculés par le code, Claude ne rédige que le résumé."""
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from . import analyze
from .render import STORES, country, e, fdelta, fnum, h, p, page, quote

THEME_LABELS = {"carte": "Carte et tracé", "direct": "Direct et vidéo", "classement": "Classements et résultats",
                "notifications": "Notifications", "connexion": "Connexion et compte", "publicité": "Publicité",
                "bug": "Plantages et lenteurs", "contenu": "Contenu", "autre": "Autres sujets"}


def dt(iso):
    return datetime.fromisoformat(iso)


def focus(counter, labeler):
    total = sum(counter.values())
    k, v = counter.most_common(1)[0]
    if total >= 3 and v >= 3 and v / total >= 0.6:
        return f"surtout {labeler(k)} ({v} sur {total})"
    return ""


def text_of(r):
    t = r["a"].get("fr") or f"{r.get('title', '')}. {r.get('text', '')}".strip(". ")
    return t if len(t) <= 220 else t[:217].rstrip() + "…"


def meta_of(r):
    return f"{STORES[r['store']]} · {country(r['country'])} · {r['rating']}/5"


def compute(cfg, recs, now, day):
    tz = ZoneInfo(cfg["timezone"])
    by = defaultdict(list)
    for r in recs.values():
        by[dt(r["date"]).astimezone(tz).date()].append(r)

    rows = []
    for app in cfg["apps"]:
        for store in ("ios", "android"):
            if not (app.get("ios_id") if store == "ios" else app.get("android_package")):
                continue

            def sel(d, app=app, store=store):
                return [r for r in by.get(d, []) if r["app"] == app["name"] and r["store"] == store]

            cur, prev = sel(day), sel(day - timedelta(days=1))
            hist = [len(sel(day - timedelta(days=k))) for k in range(1, 8)]
            base = sum(hist) / 7 if sum(1 for x in hist if x) >= 3 else None

            def avg(xs):
                return sum(r["rating"] for r in xs) / len(xs) if xs else None

            rows.append({
                "app": app["name"], "store": store, "n": len(cur), "avg": avg(cur),
                "delta": (avg(cur) - avg(prev)) if len(cur) >= 5 and len(prev) >= 5 else None,
                "ratio": (len(cur) / base) if base else None,
            })

    day_recs = by.get(day, [])
    neg = [r for r in day_recs if r["a"]["sentiment"] == "negative" or r["a"]["severity"] >= 3]
    groups = defaultdict(list)
    for r in neg:
        groups[(r["app"], r["a"]["theme"])].append(r)
    problems = []
    for (app, theme), rs in groups.items():
        sev = max(r["a"]["severity"] for r in rs)
        if len(rs) < cfg["report"]["min_problem"] and sev < 3:
            continue
        rs.sort(key=lambda r: (-r["a"]["severity"], -len(r.get("text", "")), -r.get("thumbs", 0)))
        problems.append({"app": app, "theme": theme, "n": len(rs), "sev": sev, "rs": rs,
                         "countries": Counter(r["country"] for r in rs),
                         "stores": Counter(r["store"] for r in rs)})
    problems.sort(key=lambda x: (-x["sev"], -x["n"]))
    problems = problems[:4]

    n_all, n_neg = len(day_recs), sum(1 for r in day_recs if r["a"]["sentiment"] == "negative")
    cstat = defaultdict(lambda: [0, 0])
    for r in day_recs:
        cstat[r["country"]][0] += 1
        cstat[r["country"]][1] += r["a"]["sentiment"] == "negative"
    watch = []
    for c, (n, ng) in cstat.items():
        if n < 10 or n_all - n < 10:
            continue
        rate, others = ng / n, (n_neg - ng) / (n_all - n)
        if rate >= max(0.4, 2 * others):
            watch.append({"country": c, "n": n, "rate": rate, "others": others})
    watch.sort(key=lambda x: -x["rate"])

    start = datetime.combine(day, time.min, tz)
    late = [r for r in recs.values()
            if dt(r["date"]) < start and dt(r["first_seen"]) >= now - timedelta(hours=24)]

    positives = sorted([r for r in day_recs if r["rating"] == 5 and 25 <= len(r.get("text", "")) <= 200],
                       key=lambda r: -len(r["text"]))
    return {"rows": rows, "problems": problems, "watch": watch, "late": late, "n": n_all,
            "n_neg": n_neg, "positives": positives, "day_recs": day_recs}


def _problem_line(pb):
    parts = [f"{pb['n']} avis négatifs"]
    for c, lab in ((pb["countries"], country), (pb["stores"], lambda s: STORES[s])):
        f = focus(c, lab)
        if f:
            parts.append(f)
    return " · ".join(parts)


def summary_lines(cfg, ctx, day, use_llm):
    rows, problems = ctx["rows"], ctx["problems"]
    n = sum(r["n"] for r in rows)
    avg = (sum(r["avg"] * r["n"] for r in rows if r["avg"]) / n) if n else None
    facts = {
        "evenement": cfg["name"], "jour": str(day), "avis_du_jour": n,
        "note_moyenne": round(avg, 2) if avg else None,
        "problemes": [{"sujet": THEME_LABELS[x["theme"]], "avis_negatifs": x["n"], "details": _problem_line(x)}
                      for x in problems],
        "pays_a_surveiller": [{"pays": country(w["country"]), "part_negatifs": round(w["rate"], 2)}
                              for w in ctx["watch"]],
        "avis_tardifs": len(ctx["late"]),
    }
    if use_llm and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            out = analyze.llm_text(
                cfg["models"]["summary"],
                "Tu rédiges le résumé d'un email quotidien pour une équipe produit. Écris 2 ou 3 lignes courtes, "
                "en français, factuelles, la plus importante d'abord. Utilise uniquement les chiffres fournis, "
                "n'invente rien. Une ligne par phrase, sans puces ni titre.",
                json.dumps(facts, ensure_ascii=False), max_tokens=400)
            lines = [ln.strip("-• ").strip() for ln in out.splitlines() if ln.strip()]
            if lines:
                return lines[:3]
        except Exception as ex:  # noqa: BLE001
            print(f"Résumé Claude en échec ({type(ex).__name__}), résumé standard")
    if not n:
        return ["Aucun avis publié ce jour-là sur les sources surveillées."]
    lines = [f"{n} avis, note moyenne {fnum(avg)}/5."]
    if problems:
        top = problems[0]
        lines.append(f"Sujet principal : {THEME_LABELS[top['theme']].lower()} ({_problem_line(top)}).")
    else:
        lines.append("Aucun problème notable.")
    if ctx["watch"]:
        w = ctx["watch"][0]
        lines.append(f"À surveiller : {country(w['country'])}, {round(w['rate'] * 100)} % d'avis négatifs.")
    return lines[:3]


def build_daily(cfg, recs, now, day, errors, use_llm, test=False):
    ctx = compute(cfg, recs, now, day)
    lines = summary_lines(cfg, ctx, day, use_llm)
    problems, watch, late = ctx["problems"], ctx["watch"], ctx["late"]

    blocks = [h("En bref")] + [p(e(ln)) for ln in lines]

    blocks.append(h("Chiffres du jour"))
    for r in ctx["rows"]:
        if not r["n"]:
            blocks.append(p(f"<b>{STORES[r['store']]}</b> : aucun avis."))
            continue
        bits = [f"note <b>{fnum(r['avg'])}</b>" + (f" ({fdelta(r['delta'])} vs la veille)" if r["delta"] is not None else ""),
                f"{r['n']} avis" + (f" ({fnum(r['ratio'])}× la normale)" if r["ratio"] and (r["ratio"] >= 1.5 or r["ratio"] <= 0.5) else "")]
        blocks.append(p(f"<b>{STORES[r['store']]}</b> : " + ", ".join(bits)))

    blocks.append(h("Problèmes"))
    if problems:
        for pb in problems:
            blocks.append(p(f"<b>{e(THEME_LABELS[pb['theme']])}</b> · {e(_problem_line(pb))}"))
            blocks.append(quote(text_of(pb["rs"][0]), meta_of(pb["rs"][0])))
    else:
        blocks.append(p("Rien à signaler."))
    for w in watch:
        blocks.append(p(f"<b>{e(country(w['country']))}</b> : {round(w['rate'] * 100)} % d'avis négatifs "
                        f"({w['n']} avis) contre {round(w['others'] * 100)} % ailleurs."))

    if late:
        lneg = sum(1 for r in late if r["a"]["sentiment"] == "negative")
        themes = Counter(r["a"]["theme"] for r in late if r["a"]["sentiment"] == "negative").most_common(2)
        d0, d1 = min(dt(r["date"]) for r in late), max(dt(r["date"]) for r in late)
        tz = ZoneInfo(cfg["timezone"])
        txt = (f"{len(late)} avis arrivés en retard (publiés entre le {d0.astimezone(tz):%d/%m} et le "
               f"{d1.astimezone(tz):%d/%m}), dont {lneg} négatifs")
        if themes:
            txt += " : surtout " + ", ".join(f"{THEME_LABELS[t].lower()} ({c})" for t, c in themes)
        blocks += [h("Avis tardifs"), p(e(txt) + ".")]

    picks = [pb["rs"][1] for pb in problems[:2] if len(pb["rs"]) > 1] + ctx["positives"][:1]
    if picks:
        blocks.append(h("Autres avis représentatifs"))
        blocks += [quote(text_of(r), meta_of(r)) for r in picks]

    if errors:
        blocks.append(p("⚠ Collecte incomplète : " + e("; ".join(errors[:6])), "color:#B42318;margin-top:18px"))
    markets = ", ".join(m["country"].upper() for m in cfg["markets"])
    blocks.append(p(f"{ctx['n']} avis analysés pour la journée · pays : {markets}",
                    "font-size:12px;color:#5B6270;margin-top:22px"))

    prefix = "[TEST] " if test else ""
    nb = f"{len(problems)} problème{'s' if len(problems) > 1 else ''}" if problems else "RAS"
    subject = f"{prefix}Veille avis {cfg['name']} · {day:%d/%m} · {nb}" + (" · ⚠ collecte incomplète" if errors else "")
    html = page(f"Veille des avis · {cfg['name']}", f"Activité du {day:%d/%m/%Y}", blocks)
    return subject, html, _to_text(blocks)


def _to_text(blocks):
    import re
    s = "\n".join(blocks).replace("</div>", "\n")
    s = re.sub(r"<[^>]+>", "", s)
    from html import unescape
    return re.sub(r"\n{3,}", "\n\n", unescape(s)).strip()
