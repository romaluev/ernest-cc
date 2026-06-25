#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    log_path = ROOT / "logs" / "learning-proposals.jsonl"
    if log_path.exists():
        log_path.unlink()

    payload = {
        "transcript": "CEO: I keep manually checking investor follow-ups every Friday. Ernest should automate this.",
        "session_id": "test-session",
    }
    proc = subprocess.run(
        [sys.executable, str(ROOT / "hooks" / "capture_learnings.py")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(ROOT),
        check=False,
    )
    checks: list[str] = []
    if proc.returncode != 0:
        checks.append(f"hook exited {proc.returncode}: {proc.stderr}")
    if not log_path.exists():
        checks.append("learning log was not created")
    else:
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        if len(lines) != 1:
            checks.append(f"expected 1 log line, got {len(lines)}")
        else:
            entry = json.loads(lines[0])
            if entry.get("status") != "proposed":
                checks.append("entry was not proposal-only")
            if entry.get("approval_level") != "L2":
                checks.append("proposal did not require approval")
            if "investor follow-ups" not in entry.get("observed_pattern", ""):
                checks.append("observed pattern not captured")

    if checks:
        print("FAILED:")
        for check in checks:
            print(f"  - {check}")
        return 1
    print("PASS - learning hook captured proposal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
