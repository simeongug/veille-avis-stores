"""Règle la période d'envoi automatique et les destinataires d'une épreuve dans son fichier de config."""
import argparse
import re
import sys
from datetime import date

EMAIL = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")


def _check(v):
    """Accepte JJ/MM/AAAA (aussi avec - ou .) ou AAAA-MM-JJ ; renvoie AAAA-MM-JJ pour la config."""
    v = (v or "").strip()
    if not v:
        return ""
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", v)
    try:
        d = date(int(m[3]), int(m[2]), int(m[1])) if m else date.fromisoformat(v)
    except ValueError:
        sys.exit(f"Date invalide : « {v} » (format attendu JJ/MM/AAAA, ex. 04/07/2027)")
    return d.isoformat()


def _fr(iso):
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


def _set_recipients(txt, section, emails):
    """Remplace la ligne « recipients » de la section (report ou alerts)."""
    m = re.search(rf"^{section}:\n(?:[ \t]+.*\n|\n)*?[ \t]+recipients:[^\n]*", txt, flags=re.M)
    if not m:
        sys.exit(f"recipients introuvable dans la section « {section} »")
    line = re.search(r"([ \t]+)recipients:[^\n]*$", m.group(0)).group(0)
    new = re.sub(r"recipients:[^\n]*$", "recipients: [" + ", ".join(emails) + "]", line)
    return txt[:m.end() - len(line)] + new + txt[m.end():]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--from", dest="start", default="")
    ap.add_argument("--to", dest="end", default="")
    ap.add_argument("--disable", action="store_true", help="désactive les envois automatiques")
    ap.add_argument("--recipients", default="", help="adresses séparées par des virgules ou des espaces")
    a = ap.parse_args(argv)
    start, end = _check(a.start.strip()), _check(a.end.strip())
    emails = [x for x in re.split(r"[,;\s]+", a.recipients.strip()) if x]
    bad = [x for x in emails if not EMAIL.match(x)]
    if bad:
        sys.exit("Adresse(s) invalide(s) : " + ", ".join(bad))
    if bool(start) != bool(end):
        sys.exit("Renseigne les deux dates (début et fin).")
    if start and start > end:
        sys.exit("La date de début est après la date de fin.")
    if not (start or a.disable or emails):
        sys.exit("Rien à modifier : renseigne des dates, des destinataires, ou coche « désactiver ».")
    txt = open(a.config, encoding="utf-8").read()
    msgs = []
    if start or a.disable:
        for key, val in (("active_from", start), ("active_to", end)):
            txt, n = re.subn(rf"^{key}:.*$", f"{key}: {val}".rstrip(), txt, count=1, flags=re.M)
            if not n:
                sys.exit(f"{key} introuvable dans {a.config}")
        msgs.append(f"envois automatiques du {_fr(start)} au {_fr(end)}" if start else "envois automatiques désactivés")
    if emails:
        txt = _set_recipients(_set_recipients(txt, "report", emails), "alerts", emails)
        msgs.append("destinataires du rapport et des alertes : " + ", ".join(emails))
    open(a.config, "w", encoding="utf-8").write(txt)
    print(f"{a.config} : " + " ; ".join(msgs))


if __name__ == "__main__":
    main()
