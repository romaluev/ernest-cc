"""Self-improvement: capture signals, never auto-apply.

Two entry points:
  - `capture(payload)` is called by the Stop hook after a session. It records a
    proposal candidate when it sees a repetition signal.
  - `add_note` / `summarize` back the `ernest learn` command, turning captured
    candidates into a single reviewable proposal list.

Everything here is proposal-only. Skills, configs, and permissions are never
edited automatically; that requires explicit CEO approval (L2+).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .config import Config

SIGNAL_RE = re.compile(
    r"(?i)(keep manually|manually checking|do this every|every (?:day|week|monday|friday)|"
    r"repeat|recurring|should automate|automate this|new automation|always have to)"
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _proposals_path(cfg: Config) -> Path:
    return cfg.logs_dir / "learning-proposals.jsonl"


def _extract_pattern(text: str) -> str:
    compact = " ".join(text.split())
    if len(compact) <= 240:
        return compact
    match = SIGNAL_RE.search(compact)
    if not match:
        return compact[:240]
    start = max(0, match.start() - 80)
    end = min(len(compact), match.end() + 160)
    return compact[start:end]


def make_entry(pattern: str, session_id: str = "manual") -> Dict[str, object]:
    return {
        "captured_at": _now(),
        "session_id": session_id,
        "observed_pattern": _extract_pattern(pattern),
        "change_type": "proposal",
        "target": "ernest-use-case-author",
        "approval_level": "L2",
        "status": "proposed",
        "auto_applied": False,
        "next_step": "Run /ernest-learn (or `ernest learn`) to review and approve a skill/config change.",
    }


def capture(payload: Dict[str, object], log_path: Path) -> Optional[Dict[str, object]]:
    """Record a proposal candidate if the transcript shows a repetition signal."""
    text = ""
    for key in ("transcript", "conversation", "summary", "prompt"):
        value = payload.get(key)
        if isinstance(value, str):
            text = value
            break
    if not text:
        text = json.dumps(payload, ensure_ascii=False)
    if not SIGNAL_RE.search(text):
        return None
    entry = make_entry(text, str(payload.get("session_id") or payload.get("sessionId") or "unknown"))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def add_note(cfg: Config, note: str) -> Dict[str, object]:
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)
    entry = make_entry(note)
    with _proposals_path(cfg).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def _load_entries(cfg: Config) -> List[Dict[str, object]]:
    path = _proposals_path(cfg)
    if not path.is_file():
        return []
    entries: List[Dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def summarize(cfg: Config) -> Path:
    entries = _load_entries(cfg)
    lines = [
        f"# Learning proposals - {cfg.today.isoformat()}",
        "",
        "These are candidates only. Nothing has been changed.",
        f"Each needs approval (L2) before becoming a skill or config change.",
        f"open proposals: {len(entries)}",
        "",
    ]
    if not entries:
        lines.append("- No proposals captured yet.")
    for n, entry in enumerate(entries, 1):
        lines += [
            f"## {n}. {entry.get('observed_pattern', '')}",
            f"- status: {entry.get('status', 'proposed')}",
            f"- approval: {entry.get('approval_level', 'L2')} (CEO must approve)",
            f"- target: {entry.get('target', 'ernest-use-case-author')}",
            f"- next: {entry.get('next_step', '')}",
            "",
        ]
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)
    path = cfg.logs_dir / "learning-summary.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
