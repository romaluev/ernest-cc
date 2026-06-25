#!/usr/bin/env python3
"""Stop hook: capture self-improvement candidates from completed sessions.

Thin adapter over `ernest.learn.capture`. It records proposal candidates for
`/ernest-learn`, but never edits skills, configs, credentials, or permissions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ernest.learn import capture  # noqa: E402

LOG_PATH = ROOT / "logs" / "learning-proposals.jsonl"


def _read_payload() -> Dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"transcript": raw}
    return payload if isinstance(payload, dict) else {"transcript": str(payload)}


def main() -> int:
    entry = capture(_read_payload(), LOG_PATH)
    if entry is None:
        print("{}")
        return 0
    print(json.dumps({"learningProposalCaptured": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
