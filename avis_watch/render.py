from html import escape as e

BASE = "font-family:Arial,Helvetica,sans-serif;color:#14181F;font-size:15px;line-height:1.5"

COUNTRIES = {"fr": "France", "be": "Belgique", "ch": "Suisse", "lu": "Luxembourg", "es": "Espagne",
             "it": "Italie", "gb": "Royaume-Uni", "us": "États-Unis", "nl": "Pays-Bas", "de": "Allemagne"}
STORES = {"ios": "App Store", "android": "Google Play"}


def country(c):
    return COUNTRIES.get(c, c.upper())


def fnum(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def fdelta(x):
    if round(x, 1) == 0:
        return "stable"
    return ("+" if x > 0 else "−") + fnum(abs(x))


def page(title, subtitle, blocks, accent="#14181F"):
    return (
        '<!doctype html><html lang="fr"><body style="margin:0;background:#F6F4EE">'
        f'<div style="max-width:600px;margin:0 auto;background:#FFFFFF;{BASE}">'
        f'<div style="background:{accent};color:#FFFFFF;padding:20px 28px">'
        f'<div style="font-size:21px;font-weight:bold">{e(title)}</div>'
        f'<div style="font-size:13px;color:#D5D8DF;margin-top:4px">{e(subtitle)}</div></div>'
        f'<div style="padding:4px 28px 24px">{"".join(blocks)}</div></div></body></html>'
    )


def h(t):
    return (f'<div style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;'
            f'color:#5B6270;margin:22px 0 8px;font-weight:bold">{e(t)}</div>')


def p(t, style=""):
    return f'<div style="margin:4px 0;{style}">{t}</div>'


def quote(text, meta):
    return (f'<div style="border-left:3px solid #C9CDD6;padding:2px 0 2px 12px;margin:8px 0">'
            f'<div style="font-size:12px;color:#5B6270">{e(meta)}</div>'
            f'<div>« {e(text)} »</div></div>')
