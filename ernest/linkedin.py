"""LinkedIn auto-mode glue: keep the invitation queue fresh without being asked.

The adapter under `adapters/linkedin/` does the work and runs OUTSIDE the gate.
This module is the engine's opt-in hook into it, used by `ernest start` so the
morning brief reads a queue refreshed this morning rather than last month's.

Opt-in on purpose. Spawning a browser is not something a report command should
start doing by surprise, so it stays off until `ernest.yaml` says:

    linkedin_policy:
      auto_ingest: true

Failure here is never fatal. A stale queue with an honest `source:` label beats a
crashed brief, and the card and `ernest doctor` both surface the staleness.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .config import Config

DEFAULT_MAX_AGE_HOURS = 20.0
_TIMEOUT_SECONDS = 300


def _policy_flag(cfg: Config, key: str, default: bool = False) -> bool:
    for path in (cfg.profile_dir / "ernest.yaml",
                 Path(__file__).resolve().parents[1] / "ernest.yaml"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        block = re.search(r"^linkedin_policy:\n((?:[ \t]+.*\n|\n)*)", text, re.M)
        if not block:
            continue
        m = re.search(rf"^\s+{key}:\s*(\S+)", block.group(1), re.M)
        if m:
            return m.group(1).strip().lower() in ("true", "yes", "on", "1")
        return default
    return default


def _max_age_hours(cfg: Config) -> float:
    for path in (cfg.profile_dir / "ernest.yaml",
                 Path(__file__).resolve().parents[1] / "ernest.yaml"):
        try:
            m = re.search(r"^\s+ingest_max_age_hours:\s*([\d.]+)",
                          path.read_text(encoding="utf-8"), re.M)
        except OSError:
            continue
        if m:
            return float(m.group(1))
    return DEFAULT_MAX_AGE_HOURS


def queue_age_hours(cfg: Config) -> Optional[float]:
    """None when there is no queue at all — which is not the same as a stale one."""
    li = cfg.data_dir / "linkedin"
    csvs = sorted(li.glob("*.csv")) if li.is_dir() else []
    if not csvs:
        return None
    return (time.time() - max(p.stat().st_mtime for p in csvs)) / 3600.0


def _adapter(cfg: Config) -> Optional[Path]:
    for root in (cfg.profile_dir, Path(__file__).resolve().parents[1]):
        candidate = root / "adapters" / "linkedin" / "ingest.py"
        if candidate.is_file():
            return candidate
    return None


def refresh_if_stale(cfg: Config, *, force: bool = False) -> Dict[str, Any]:
    """Walk the ingest ladder when the queue is older than the policy allows.

    Returns a status dict; callers print it and move on. Never raises.
    """
    if not force and not _policy_flag(cfg, "auto_ingest"):
        return {"ran": False, "why": "auto_ingest is off in ernest.yaml"}
    age = queue_age_hours(cfg)
    limit = _max_age_hours(cfg)
    if not force and age is not None and age <= limit:
        return {"ran": False, "why": f"queue is {age:.1f}h old (limit {limit:.0f}h)"}
    script = _adapter(cfg)
    if script is None:
        return {"ran": False, "why": "adapters/linkedin/ingest.py not found"}
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "--profile-dir", str(cfg.profile_dir), "--agent"],
            capture_output=True, text=True, timeout=_TIMEOUT_SECONDS)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"ran": True, "ok": False, "why": f"ingest did not finish ({exc})"}
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"ran": True, "ok": False, "exit": proc.returncode,
                "why": (proc.stderr or proc.stdout).strip()[:200] or "no output"}
    meta, results = payload.get("meta", {}), payload.get("results", {})
    return {"ran": True, "ok": bool(results.get("ok")), "exit": proc.returncode,
            "source": meta.get("source"), "rung": meta.get("rung"),
            "rows": results.get("rows"),
            "why": results.get("remedy") or meta.get("reason") or ""}


def summary_line(status: Dict[str, Any]) -> Optional[str]:
    """One line for the start output, or None when there is nothing worth saying."""
    if not status.get("ran"):
        return None
    if status.get("ok"):
        return (f"LinkedIn: refreshed {status.get('rows')} invitation(s) "
                f"via rung {status.get('rung')} ({status.get('source')}).")
    return f"⚠ LinkedIn refresh failed — working from the last queue. {status.get('why', '')}".strip()
