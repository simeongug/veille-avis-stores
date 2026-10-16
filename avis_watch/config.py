import os

import yaml

DEFAULTS = {
    "timezone": "Europe/Paris",
    "rescan_days": 14,
    "themes": ["carte", "direct", "classement", "notifications", "connexion",
               "publicité", "bug", "contenu", "autre"],
    "report": {"recipients": [], "min_problem": 3},
    "alerts": {
        "recipients": [], "window_minutes": 60, "volume_min": 15, "volume_factor": 4,
        "rating_below": 3.0, "rating_min_reviews": 8, "rating_window_hours": 3,
        "theme_min": 8, "cooldown_minutes": 180,
    },
    "models": {"classify": "claude-haiku-5-5", "summary": "claude-sonnet-5-5"},
}


def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load(path, data_dir="data"):
    with open(path, encoding="utf-8") as f:
        cfg = _merge(DEFAULTS, yaml.safe_load(f))
    cfg["data_dir"] = os.path.join(data_dir, cfg["event"])
    return cfg
