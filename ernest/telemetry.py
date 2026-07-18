"""Usage telemetry: the raw signal the improvement loop learns from.

Every engine command appends one JSONL line to `logs/usage.jsonl` (the Hermes
`.usage.json` analog — see docs/research/self-improving-systems.md). Local-only,
append-only, no content: counts and ids, never bodies. `concern_stats` derives
per-concern activity (last fired, total items, active days) so `ernest learn`
can spot dead concerns (stale-30d pattern) and measure applied changes.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .config import Config

_ITEMS_RE = re.compile(r"^items:\s*(\d+)\s*$", re.M)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_path(cfg: Config) -> Path:
    return cfg.logs_dir / "usage.jsonl"


def log(cfg: Config, cmd: str, **fields: object) -> None:
    """Append one usage event. Never raises — telemetry must not break the engine."""
    try:
        cfg.logs_dir.mkdir(parents=True, exist_ok=True)
        entry: Dict[str, object] = {"at": _now(), "day": cfg.today.isoformat(), "cmd": cmd}
        entry.update({k: v for k, v in fields.items() if v is not None})
        with log_path(cfg).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def card_items(path: Path) -> int:
    """Read the `items: N` header the engine writes into every card."""
    try:
        match = _ITEMS_RE.search(path.read_text(encoding="utf-8"))
        return int(match.group(1)) if match else 0
    except (OSError, ValueError):
        return 0


def load(cfg: Config) -> List[Dict[str, object]]:
    path = log_path(cfg)
    if not path.is_file():
        return []
    out: List[Dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def concern_stats(cfg: Config) -> Dict[str, Dict[str, object]]:
    """Per-concern activity derived from watch events:
    {concern: {last_fired, first_seen, runs, items_total, active_days}}."""
    stats: Dict[str, Dict[str, object]] = {}
    for entry in load(cfg):
        if entry.get("cmd") != "watch":
            continue
        day = str(entry.get("day", ""))
        for concern, items in (entry.get("concerns") or {}).items():
            s = stats.setdefault(concern, {"first_seen": day, "last_fired": None,
                                           "runs": 0, "items_total": 0, "days": set()})
            s["runs"] = int(s["runs"]) + 1
            s["days"].add(day)  # type: ignore[union-attr]
            if int(items) > 0:
                s["items_total"] = int(s["items_total"]) + int(items)
                if s["last_fired"] is None or day > str(s["last_fired"]):
                    s["last_fired"] = day
    for s in stats.values():
        s["active_days"] = len(s.pop("days"))  # type: ignore[arg-type]
    return stats


def days_since(cfg: Config, day: Optional[str]) -> Optional[int]:
    if not day:
        return None
    try:
        return (cfg.today - date.fromisoformat(str(day))).days
    except ValueError:
        return None
