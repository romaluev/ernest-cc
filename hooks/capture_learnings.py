#!/usr/bin/env python3
"""Capture self-improvement candidates from completed sessions.

This Stop hook is intentionally conservative: it records proposal candidates for
`/ernest-learn`, but never edits skills, configs, credentials, or permissions.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "logs" / "learning-proposals.jsonl"

_SIGNAL_RE = re.compile(
    r"(?i)(keep manually|manually checking|do this every|repeat|recurring|"
    r"should automate|automate this|new automation|always have to)"
)


def _read_payload() -> Dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"transcript": raw}
    return payload if isinstance(payload, dict) else {"transcript": str(payload)}


def _transcript(payload: Dict[str, Any]) -> str:
    for key in ("transcript", "conversation", "summary", "prompt"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return json.dumps(payload, ensure_ascii=False)


def _extract_pattern(text: str) -> str:
    compact = " ".join(text.split())
    if len(compact) <= 240:
        return compact
    match = _SIGNAL_RE.search(compact)
    if not match:
        return compact[:240]
    start = max(0, match.start() - 80)
    end = min(len(compact), match.end() + 160)
    return compact[start:end]


def main() -> int:
    payload = _read_payload()
    text = _transcript(payload)
    if not _SIGNAL_RE.search(text):
        print("{}")
        return 0

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session_id": payload.get("session_id") or payload.get("sessionId") or "unknown",
        "observed_pattern": _extract_pattern(text),
        "change_type": "proposal",
        "target": "ernest-use-case-author",
        "approval_level": "L2",
        "status": "proposed",
        "auto_applied": False,
        "next_step": "Run /ernest-learn to turn this into a reviewed skill/config proposal.",
    }
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(json.dumps({"learningProposalCaptured": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
