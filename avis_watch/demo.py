"""Données fictives pour tester le rapport et les alertes sans aucun accès réseau."""
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TEXTS = {
    "pos": ["Le direct est enfin fluide, et le classement se met à jour tout seul.",
            "Super application pour suivre chaque étape, bravo à l'équipe.",
            "Très complète : résultats, coureurs et vidéos au même endroit.",
            "Rien à redire, je la recommande à tous les fans de cyclisme."],
    "neutre": ["Correcte, mais manque quelques options.", "Pas mal, peut mieux faire."],
    "carte_es": ["El mapa no carga durante la llegada, pantalla en blanco.",
                 "No se ve el trazado de la etapa, el mapa no funciona.",
                 "Desde la actualización el mapa se queda en blanco."],
    "notif": ["Chaque notification arrive en double, c'est pénible pendant les étapes.",
              "Les notifications arrivent en anglais et en double."],
    "idee": ["Il faudrait pouvoir choisir les équipes suivies pour les notifications.",
             "J'aimerais voir le profil de l'étape avec la position des coureurs."],
    "carte_fr": ["La carte ne charge pas au moment du sprint, écran blanc."],
}


def populate(cfg, recs, now, seed=7):
    rnd = random.Random(seed)
    tz = ZoneInfo(cfg["timezone"])
    app = cfg["apps"][0]["name"]
    day = (now.astimezone(tz) - timedelta(days=1)).date()
    n = [0]

    def add(d, hour, store, ctry, rating, text, first_seen=None, minute=None):
        n[0] += 1
        when = datetime(d.year, d.month, d.day, hour, minute if minute is not None else rnd.randint(0, 59), tzinfo=tz)
        r = {"id": f"{store}:{ctry}:demo{n[0]}", "app": app, "store": store, "country": ctry, "lang": ctry,
             "rating": rating, "title": "", "text": text, "date": when.astimezone(now.tzinfo).isoformat(),
             "version": "9.9", "thumbs": rnd.randint(0, 5),
             "first_seen": (first_seen or when.astimezone(now.tzinfo)).isoformat()}
        recs[r["id"]] = r

    for k in range(1, 9):  # historique normal
        d = day - timedelta(days=k)
        for _ in range(rnd.randint(28, 40)):
            store = rnd.choice(["ios", "android"])
            ctry = rnd.choice(["fr", "fr", "fr", "be", "es", "gb"])
            good = rnd.random() < 0.8
            add(d, rnd.randint(8, 22), store, ctry, rnd.choice([4, 5, 5]) if good else rnd.choice([1, 2, 3]),
                rnd.choice(TEXTS["pos"] if good else TEXTS["neutre"]))
    for _ in range(95):  # hier : majorité positive
        add(day, rnd.randint(8, 22), rnd.choice(["ios", "android"]), rnd.choice(["fr", "fr", "be", "gb"]),
            rnd.choice([4, 5, 5]), rnd.choice(TEXTS["pos"]))
    for _ in range(18):  # hier : problème de carte concentré en Espagne sur Android
        add(day, rnd.randint(16, 18), "android", "es", rnd.choice([1, 1, 2]), rnd.choice(TEXTS["carte_es"]))
    for _ in range(7):   # hier : notifications sur iOS en France
        add(day, rnd.randint(9, 20), "ios", "fr", rnd.choice([1, 2]), rnd.choice(TEXTS["notif"]))
    for _ in range(5):   # hier : demandes d'amélioration
        add(day, rnd.randint(9, 20), rnd.choice(["ios", "android"]), "fr", 2, rnd.choice(TEXTS["idee"]))
    for _ in range(6):   # avis tardifs arrivés ce matin
        add(day - timedelta(days=rnd.randint(1, 3)), rnd.randint(10, 20), "android", "fr", rnd.choice([1, 2]),
            rnd.choice(TEXTS["carte_fr"]), first_seen=now - timedelta(hours=3))
    today = now.astimezone(tz).date()  # pic récent pour tester l'alerte
    for i in range(30):
        add(today, now.astimezone(tz).hour, "android", rnd.choice(["es", "es", "fr"]), 1,
            rnd.choice(TEXTS["carte_es"] + TEXTS["carte_fr"]), first_seen=now - timedelta(minutes=rnd.randint(1, 50)),
            minute=max(0, now.astimezone(tz).minute - rnd.randint(0, 45)) if now.astimezone(tz).minute >= 45 else 0)
    # les dates « aujourd'hui » ne doivent pas être dans le futur
    for r in recs.values():
        if datetime.fromisoformat(r["date"]) > now:
            r["date"] = now.isoformat()
