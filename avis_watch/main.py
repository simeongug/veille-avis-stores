import argparse
import sys
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import alerts, analyze, config, mailer, report, store


def _parse_as_of(v):
    """Rejeu : JJ/MM/AAAA HH:MM (heure facultative, 9 h par défaut) ou AAAA-MM-JJTHH:MM."""
    import re
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?:[ T]+(\d{1,2})[:h](\d{2})?)?", v.strip())
    if m:
        return datetime(int(m[3]), int(m[2]), int(m[1]), int(m[4] or 9), int(m[5] or 0))
    return datetime.fromisoformat(v.strip())


def _in_window(cfg, today):
    a, b = cfg.get("active_from"), cfg.get("active_to")
    if not a or not b:
        return False
    a = a if isinstance(a, date) else date.fromisoformat(str(a))
    b = b if isinstance(b, date) else date.fromisoformat(str(b))
    return a <= today <= b


def _gather(cfg, args, now, days):
    """Collecte (ou démo), fusion, analyse, sauvegarde. Retourne (avis, erreurs)."""
    recs = store.load(cfg)
    seed = not recs
    if args.demo:
        from . import demo
        demo.populate(cfg, recs, now)
        fetched, errors = [], []
    else:
        from . import collect
        since = now - timedelta(days=days)
        only = None
        if args.command == "alert" and not args.as_of:  # alertes : pays et langues actifs seulement
            only = store.read_json(cfg, "active.json", None)
            if only:
                print(f"Collecte légère : {len(only.get('ios', []))} pays App Store, "
                      f"{len(only.get('android', []))} langues Google Play actifs récemment")
        fetched, errors = collect.collect_all(cfg, since=since, max_count=6000 if args.as_of else 1500, only=only)
        if args.as_of:  # rejeu : les flux ne donnent que les avis les plus récents, l'historique peut ne pas remonter assez
            from .render import STORES
            for st, name in STORES.items():
                dates = [datetime.fromisoformat(r["date"]) for r in fetched if r["store"] == st]
                if dates and min(dates) > since:
                    errors.append(f"{name} : l'historique public ne remonte qu'au "
                                  f"{min(dates).astimezone(ZoneInfo(cfg['timezone'])):%d/%m/%Y}, des avis plus anciens sont introuvables")
        fetched = [r for r in fetched if datetime.fromisoformat(r["date"]) >= since]
        if args.as_of:  # rejeu : on ignore les avis publiés après la date simulée
            fetched = [r for r in fetched if datetime.fromisoformat(r["date"]) <= now]
    new =store.merge(recs, fetched, now.isoformat(), seed)
    t = time.time()
    n = analyze.classify(cfg, list(recs.values()), use_llm=not args.no_llm, now=now)
    print(f"⏱ Analyse : {time.time() - t:.0f} s")
    store.save(cfg, recs)
    if args.command != "alert" and not args.demo:  # collecte complète : on note les pays et langues actifs
        store.write_json(cfg, "active.json", _active(recs, now))
    print(f"{len(new)} nouveaux avis, {n} analysés, {len(recs)} au total, {len(errors)} source(s) en échec")
    return recs, errors


def _active(recs, now, days=60):
    """Pays App Store et langues Google Play ayant reçu au moins un avis sur les N derniers jours."""
    lim = now - timedelta(days=days)
    rs = [r for r in recs.values() if datetime.fromisoformat(r["date"]) >= lim]
    return {"ios": sorted({r["country"] for r in rs if r["store"] == "ios"}),
            "android": sorted({r["lang"] for r in rs if r["store"] == "android" and r.get("lang")})}


def _ratings(cfg, args, local):
    """Moyenne globale des stores du jour et dernier relevé précédent (pour la variation)."""
    if args.demo:
        return {"ios": {"avg": 4.31, "count": 590}, "android": {"avg": 4.12, "count": 17800}}, \
               {"ios": {"avg": 4.30, "count": 585}, "android": {"avg": 4.13, "count": 17700}}
    from . import collect
    ratings = collect.fetch_ratings(cfg) or None
    hist = store.read_json(cfg, "ratings.json", {})
    today = str(local.date())
    earlier = sorted(d for d in hist if d < today)
    prev = hist[earlier[-1]] if earlier else None
    if ratings:
        hist[today] = ratings
        store.write_json(cfg, "ratings.json", hist)
    return ratings, prev


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["daily", "alert", "collect"])
    ap.add_argument("--config", default="config/tour-de-france.yml")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--demo", action="store_true", help="données fictives, aucun accès réseau")
    ap.add_argument("--dry-run", action="store_true", help="écrit l'email dans out/ au lieu de l'envoyer")
    ap.add_argument("--no-llm", action="store_true", help="n'appelle pas Claude (analyse par mots-clés)")
    ap.add_argument("--to", default=None, help="destinataire(s) de test, séparés par des virgules")
    ap.add_argument("--scheduled", action="store_true", help="applique la fenêtre d'activité et l'heure d'envoi")
    ap.add_argument("--date", default=None, help="jour du rapport (AAAA-MM-JJ), par défaut hier")
    ap.add_argument("--as-of", default=None,
                    help="rejeu : simule la date et l'heure de Paris (ex. 2026-07-05T09:00)")
    args = ap.parse_args(argv)

    t0 = time.time()
    cfg = config.load(args.config, args.data_dir)
    tz = ZoneInfo(cfg["timezone"])
    if args.as_of:
        now = _parse_as_of(args.as_of).replace(tzinfo=tz).astimezone(timezone.utc)
    else:
        now = datetime.now(timezone.utc)
    local = now.astimezone(tz)
    test = bool(args.to) or args.demo or bool(args.as_of)
    tag = f" · rejeu du {local:%d/%m}" if args.as_of else ""

    if args.scheduled and not _in_window(cfg, local.date()):
        print("Hors de la fenêtre d'activité de l'événement : rien à faire.")
        return 0

    if args.command == "collect":
        _gather(cfg, args, now, cfg["rescan_days"])
        return 0

    if args.command == "daily":
        state = store.read_json(cfg, "state.json", {})
        if args.scheduled:
            if not (9 <= local.hour < 13) or state.get("last_daily") == str(local.date()):
                print("Pas l'heure d'envoi ou rapport déjà envoyé aujourd'hui.")
                return 0
        recs, errors = _gather(cfg, args, now, cfg["rescan_days"])
        day = date.fromisoformat(args.date) if args.date else local.date() - timedelta(days=1)
        ratings, prev = _ratings(cfg, args, local)
        t = time.time()
        subject, html, text = report.build_daily(cfg, recs, now, day, errors, not args.no_llm, test, tag,
                                                 ratings, prev)
        print(f"⏱ Rédaction de l'email (titres et accroche par l'IA) : {time.time() - t:.0f} s")
        to = args.to.split(",") if args.to else cfg["report"]["recipients"]
        t = time.time()
        mailer.send(subject, html, text, to, args.dry_run, "rapport")
        print(f"⏱ Envoi : {time.time() - t:.0f} s · Total : {time.time() - t0:.0f} s")
        if args.scheduled and not args.dry_run:
            state["last_daily"] = str(local.date())
            store.write_json(cfg, "state.json", state)
        return 0

    recs, errors = _gather(cfg, args, now, 2)
    found = alerts.check(cfg, recs, now)
    found, state = alerts.filter_cooldown(cfg, found, now)
    if not found:
        print(f"Aucune alerte. ⏱ Total : {time.time() - t0:.0f} s")
        return 0
    subject, html, text = alerts.build(cfg, found, now, test)
    to = args.to.split(",") if args.to else cfg["alerts"]["recipients"]
    mailer.send(subject, html, text, to, args.dry_run, "alerte")
    print(f"⏱ Total : {time.time() - t0:.0f} s")
    if not args.dry_run and not test:
        alerts.mark_sent(cfg, state, found, now)
    return 0


if __name__ == "__main__":
    sys.exit(main())
