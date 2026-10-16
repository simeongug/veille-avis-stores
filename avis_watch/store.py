import json
import os


def _p(cfg, name):
    return os.path.join(cfg["data_dir"], name)


def load(cfg):
    recs = {}
    p = _p(cfg, "reviews.jsonl")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    recs[r["id"]] = r
    return recs


def save(cfg, recs):
    os.makedirs(cfg["data_dir"], exist_ok=True)
    rows = sorted(recs.values(), key=lambda r: r["date"])
    with open(_p(cfg, "reviews.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def merge(recs, fetched, now_iso, seed):
    """Ajoute les avis jamais vus. Premier lancement (seed) : l'historique n'est pas
    considéré comme « nouveau » (first_seen = date de l'avis)."""
    new = []
    for r in fetched:
        if r["id"] in recs:
            continue
        r = dict(r)
        r["first_seen"] = r["date"] if seed else now_iso
        recs[r["id"]] = r
        new.append(r)
    return new


def read_json(cfg, name, default):
    p = _p(cfg, name)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return default


def write_json(cfg, name, data):
    os.makedirs(cfg["data_dir"], exist_ok=True)
    with open(_p(cfg, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
