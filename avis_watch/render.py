"""Mise en forme des emails : sobre, blanc, une seule couleur d'accent par sens (vert = bien, rouge = mal)."""
from html import escape as e

FONT = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
INK, GREY, LINE = "#111827", "#6B7280", "#E5E7EB"
GREEN, RED = "#15803D", "#B91C1C"

COUNTRIES = {"fr": "France", "be": "Belgique", "ch": "Suisse", "lu": "Luxembourg", "es": "Espagne",
             "it": "Italie", "gb": "Royaume-Uni", "us": "États-Unis", "nl": "Pays-Bas", "de": "Allemagne",
             "pt": "Portugal", "sa": "Arabie saoudite", "ae": "Émirats arabes unis"}
STORES = {"ios": "App Store", "android": "Google Play"}
DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
          "octobre", "novembre", "décembre"]


LANGS = {"fr": "en français", "en": "en anglais", "es": "en espagnol", "it": "en italien",
         "nl": "en néerlandais", "de": "en allemand",
         "pt": "en portugais", "ar": "en arabe"}


def _babel(kind, code):
    try:
        from babel import Locale
        loc = Locale("fr")
        return (loc.territories if kind == "t" else loc.languages).get(code)
    except Exception:  # noqa: BLE001
        return None


def country(c):
    """Pays (App Store) ou langue (Google Play, codée « lang:xx »)."""
    if c.startswith("lang:"):
        code = c[5:]
        if code in LANGS:
            return "avis " + LANGS[code]
        name = _babel("l", "he" if code == "iw" else code)
        return f"avis en {name}" if name else "avis " + code
    return COUNTRIES.get(c) or _babel("t", c.upper()) or c.upper()


def cap(t):
    return t[:1].upper() + t[1:]


def fnum(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def long_date(d):
    return f"{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]}"


def delta(text, tone):
    """tone : 'good' (vert), 'bad' (rouge) ou 'flat' (gris)."""
    color = {"good": GREEN, "bad": RED}.get(tone, GREY)
    return f'<span style="color:{color};font-size:12px;font-weight:600">{e(text)}</span>'


def page(title, subtitle, blocks, dot=None):
    mark = f'<span style="color:{dot}">●</span> ' if dot else ""
    return (
        '<!doctype html><html lang="fr"><body style="margin:0;padding:24px 12px;background:#FFFFFF">'
        f'<div style="max-width:560px;margin:0 auto;font-family:{FONT};color:{INK};font-size:15px;line-height:1.5">'
        f'<div style="font-size:22px;font-weight:500">{mark}{e(title)}</div>'
        f'<div style="font-size:13px;color:{GREY};margin-top:2px">{e(subtitle)}</div>'
        f'{"".join(blocks)}</div></body></html>'
    )


def h(t):
    return (f'<div style="font-size:13px;font-weight:700;margin:26px 0 8px;padding-top:14px;'
            f'border-top:1px solid {LINE}">{e(t)}</div>')


def p(t, style=""):
    return f'<div style="margin:4px 0;{style}">{t}</div>'


def quote(text, meta):
    return (f'<div style="margin:4px 0 12px;color:{GREY};font-size:14px">« {e(text)} »'
            f'<span style="font-size:12px"> · {e(meta)}</span></div>')
