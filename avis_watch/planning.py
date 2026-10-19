"""Règle la période d'envoi automatique (rapport de 9 h et alertes) d'une épreuve dans son fichier de config."""
import argparse
import re
import sys
from datetime import date


def _check(v):
    if v:
        date.fromisoformat(v)  # lève une erreur si le format n'est pas AAAA-MM-JJ
    return v or ""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--from", dest="start", default="")
    ap.add_argument("--to", dest="end", default="")
    a = ap.parse_args(argv)
    start, end = _check(a.start.strip()), _check(a.end.strip())
    if bool(start) != bool(end):
        sys.exit("Renseigne les deux dates (début et fin), ou aucune pour désactiver les envois automatiques.")
    if start and start > end:
        sys.exit("La date de début est après la date de fin.")
    txt = open(a.config, encoding="utf-8").read()
    for key, val in (("active_from", start), ("active_to", end)):
        txt, n = re.subn(rf"^{key}:.*$", f"{key}: {val}".rstrip(), txt, count=1, flags=re.M)
        if not n:
            sys.exit(f"{key} introuvable dans {a.config}")
    open(a.config, "w", encoding="utf-8").write(txt)
    print(f"{a.config} : envois automatiques " + (f"du {start} au {end}" if start else "désactivés"))


if __name__ == "__main__":
    main()
