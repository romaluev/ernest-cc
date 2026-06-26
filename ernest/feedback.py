"""Record CEO feedback signals (audit trail for the adaptive loop).

The actual preference change lives in `memory/preferences.md` (the model edits it,
L1/reversible). This module just appends a timestamped, machine-readable signal so
there is a trace, and so the weekly `ernest learn` pass can spot recurring asks.
Nothing here sends or mutates external systems.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from .config import Config


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_path(cfg: Config) -> Path:
    return cfg.logs_dir / "feedback.jsonl"


def record(cfg: Config, note: str, kind: str = "feedback") -> Dict[str, str]:
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)
    entry = {"at": _now(), "kind": kind, "note": " ".join(note.split())}
    with log_path(cfg).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry
