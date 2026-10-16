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
    "anomaly": {"baseline_days": 14, "min_reviews": 15, "volume_min": 15, "volume_factor": 3,
                "rating_low": 3.2, "rating_drop": 0.6, "baseline_min_reviews": 20, "neg_share": 0.4,
                "version_share": 0.7, "theme_min": 5, "theme_factor": 3, "silence_base_min": 8},
    "llm": {"min_interval_s": 6, "recent_days": 3},
    "models": {
        "gemini": {"classify": "gemini-3.5-flash-lite", "summary": "gemini-3.6-flash",
                   "fallbacks": ["gemini-3.1-flash-lite", "gemini-3.8-flash", "gemini-3.6-flash"]},
        "claude": {"classify": "claude-haiku-5-5", "summary": "claude-sonnet-5-5"},
    },
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
