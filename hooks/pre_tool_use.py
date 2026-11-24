#!/usr/bin/env python3
"""Claude Code PreToolUse adapter for Ernest's gate.

FAIL CLOSED: any error reading the payload or evaluating the gate results in a
deny, never a silent allow. A crashed/erroring guard must not open the door.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


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
        # O_APPEND single write so concurrent/crashing runs cannot corrupt the log.
        line = f"{timestamp}|{tool}|{decision}|{reason}\n"
        fd = os.open(str(log_dir / "enforcement-audit.log"),
                     os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    except OSError:
        pass


def _deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))


def main() -> int:
    try:
        payload = _read_payload()
        tool = _tool_name(payload)
        args = _tool_input(payload)
    except Exception as exc:  # noqa: BLE001 — fail closed on malformed input
        _audit("<unparsed>", "DENY_FAILCLOSED", f"payload error: {exc!r}")
        _deny(f"ERNEST FAIL-CLOSED: could not parse tool request ({exc!r}); denied.")
        return 0

    try:
        from ernest.gate import evaluate, load_scope
        scope = load_scope(str(ROOT))
        block = evaluate(tool, args, str(ROOT), scope=scope)
    except Exception as exc:  # noqa: BLE001 — guard error must not open the door
        _audit(tool, "DENY_FAILCLOSED", f"gate error: {exc!r}")
        _deny(f"ERNEST FAIL-CLOSED: gate raised {exc!r}; denied for safety.")
        return 0

    if block is None:
        print("{}")
        return 0

    kind = block.get("error", "blocked")
    reason = block.get("reason", "blocked by Ernest gate")
    _audit(tool, kind.upper(), reason)
    prefix = "ERNEST DRAFT ONLY" if kind == "draft_only" else "ERNEST SCOPE DENIED"
    if kind == "shell_external_mutation":
        prefix = "ERNEST SHELL DENIED"
    elif kind == "ernest_protected":
        prefix = "ERNEST GUARDRAIL PROTECTED"
    elif kind == "egress_denied":
        prefix = "ERNEST WEB OFF (confidential mode)"
    # Plain-English message to the model/CEO; full structured detail stays in the audit log.
    _deny(f"{prefix}: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
