#!/usr/bin/env python3
"""Claude Code PreToolUse adapter for Ernest's gate."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ernest.gate import evaluate, load_scope  # noqa: E402


def _read_payload() -> Dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def _tool_name(payload: Dict[str, Any]) -> str:
    return str(payload.get("tool_name") or payload.get("toolName") or payload.get("name") or "")


def _tool_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    tool_input = payload.get("tool_input", payload.get("toolInput", payload.get("input", {})))
    return tool_input if isinstance(tool_input, dict) else {}


def _audit(tool: str, decision: str, reason: str) -> None:
    try:
        log_dir = ROOT / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with (log_dir / "enforcement-audit.log").open("a", encoding="utf-8") as fh:
            fh.write(f"{timestamp}|{tool}|{decision}|{reason}\n")
    except OSError:
        pass


def main() -> int:
    payload = _read_payload()
    tool = _tool_name(payload)
    args = _tool_input(payload)
    scope = load_scope(str(ROOT))
    block = evaluate(tool, args, str(ROOT), scope=scope)
    if block is None:
        print("{}")
        return 0

    kind = block.get("error", "blocked")
    reason = block.get("reason", "blocked by Ernest gate")
    _audit(tool, kind.upper(), reason)
    prefix = "ERNEST DRAFT ONLY" if kind == "draft_only" else "ERNEST SCOPE DENIED"
    if kind == "shell_external_mutation":
        prefix = "ERNEST SHELL DENIED"
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"{prefix} {json.dumps(block, ensure_ascii=False)}",
        }
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
