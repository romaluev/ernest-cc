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


def _write_entries(cfg: Config, entries: List[Dict[str, object]]) -> None:
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)
    with _proposals_path(cfg).open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _slugify(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return "-".join(words[:4]) or "automation"


def summarize(cfg: Config) -> Path:
    entries = _load_entries(cfg)
    open_count = sum(1 for e in entries if e.get("status") == "proposed")
    lines = [
        f"# Learning proposals - {cfg.today.isoformat()}",
        "",
        "These are candidates only. Nothing has been changed automatically.",
        "Each needs CEO approval (L2) before becoming a skill or config change.",
        f"open proposals: {open_count} | total recorded: {len(entries)}",
        "",
    ]
    if not entries:
        lines.append("- No proposals captured yet.")
    for n, entry in enumerate(entries, 1):
        status = entry.get("status", "proposed")
        suggested_id = _slugify(str(entry.get("observed_pattern", "")))
        lines += [
            f"## {n}. {entry.get('observed_pattern', '')}",
            f"- status: {status}",
            f"- approval: {entry.get('approval_level', 'L2')} (CEO must approve)",
            f"- target: {entry.get('target', 'ernest-use-case-author')}",
        ]
        if status == "proposed":
            lines.append(
                f"- adopt: `ernest learn --adopt {n} --id {suggested_id} "
                f"--playbook account-followup-recovery` (or `inbox-prospect-followup`)"
            )
        elif status == "adopted":
            lines.append(f"- adopted as: {entry.get('adopted_as', '')}")
        lines.append("")
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)
    path = cfg.logs_dir / "learning-summary.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def adopt(cfg: Config, index: int, concern_id: str, playbook: str,
          staleness: Optional[str] = None, intent: Optional[str] = None,
          window: Optional[str] = None) -> Dict[str, object]:
    """Promote a proposal into a live automation. This is the approval step:
    nothing is applied until the CEO runs it explicitly."""
    from .automations import scaffold  # local import avoids a cycle

    entries = _load_entries(cfg)
    if index < 1 or index > len(entries):
        raise ValueError(f"No proposal #{index}. There are {len(entries)} recorded.")
    entry = entries[index - 1]
    description = f"Adopted from learning proposal: {entry.get('observed_pattern', '')}"
    result = scaffold(cfg, concern_id=concern_id, playbook=playbook,
                      description=description, staleness=staleness,
                      intent=intent, window=window)
    entry["status"] = "adopted"
    entry["adopted_as"] = concern_id
    entry["adopted_at"] = _now()
    _write_entries(cfg, entries)
    return {"concern_id": concern_id, "skill_path": result["skill_path"],
            "concern_added": result["concern_added"]}
