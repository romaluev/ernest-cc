"""Read the CEO's living preferences.

`memory/preferences.md` is primarily a narrative the model reads and updates as it
learns the CEO's taste. A small "Engine settings" block holds machine-read keys
(e.g. whether `ernest start` auto-renders a digest) so the deterministic engine
can honor preferences too. Missing file or keys fall back to safe defaults.
"""
from __future__ import annotations

from typing import Dict

from .config import Config

DEFAULTS: Dict[str, str] = {
    "auto_render": "on",
    "read_more_format": "html",
    "max_key_points": "6",
}


def load(cfg: Config) -> Dict[str, str]:
    prefs = dict(DEFAULTS)
    path = cfg.memory_dir / "preferences.md"
    if not path.is_file():
        return prefs
    in_settings = False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return prefs
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            in_settings = "engine settings" in stripped.lower()
            continue
        if in_settings and stripped.startswith("- ") and ":" in stripped:
            key, _, val = stripped[2:].partition(":")
            prefs[key.strip()] = val.strip()
    return prefs


def truthy(value: str) -> bool:
    return str(value).strip().lower() in ("on", "true", "yes", "1")
