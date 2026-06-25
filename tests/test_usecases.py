#!/usr/bin/env python3
"""Verify core playbooks produce correct remind/assign cards on sample data."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILURES: list[str] = []


def check(label: str, condition: bool) -> None:
    print(f"  [{'ok  ' if condition else 'FAIL'}] {label}")
    if not condition:
        FAILURES.append(label)


def main() -> int:
    profile = Path(tempfile.mkdtemp(prefix="ernest_uc_profile_"))
    vault = Path(tempfile.mkdtemp(prefix="ernest_uc_vault_"))
    shutil.copytree(ROOT / "memory", profile / "memory")
    shutil.copytree(ROOT / "data", profile / "data")

    env = os.environ.copy()
    env.update({
        "ERNEST_PROFILE_DIR": str(profile),
        "ERNEST_LOCAL_VAULT": str(vault),
        "ERNEST_MODE": "local",
        "ERNEST_TODAY": "2026-06-25",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    proc = subprocess.run([sys.executable, "-m", "ernest.cli", "watch"],
                          cwd=str(ROOT), env=env, text=True, capture_output=True, check=False)
    check("watch exits 0", proc.returncode == 0)
    if proc.returncode != 0:
        print(proc.stderr)

    watch_dir = vault / "Ernest" / "00-Watch"

    def card(concern: str) -> str:
        hits = list(watch_dir.glob(f"{concern}--*.md")) if watch_dir.exists() else []
        return "\n".join(h.read_text() for h in hits)

    all_cards = "\n".join(p.read_text() for p in watch_dir.glob("*.md")) if watch_dir.exists() else ""

    collab = card("b2b-collaborator-coverage")
    check("collaborator card exists", bool(collab))
    check("collaborator names teammate", "Alex" in collab)
    check("collaborator flags missing thread", "Acme Corp" in collab)
    check("collaborator excludes covered thread", "Horizon Ltd" not in collab)

    cand = card("b2b-candidates")
    check("candidate card exists", bool(cand))
    check("candidate flags inbox candidate", "Jordan Lee" in cand)
    check("candidate mentions assignees", "recruiting-lead" in cand)

    important = card("important-followups")
    check("important-followups card exists", bool(important))
    check("important-followups surfaces VIP account", "Apex Bank" in important)

    korea = card("korea-list-sync")
    check("list-sync card exists", bool(korea))
    check("list-sync flags CRM gap", "PacificCo" in korea)

    press = card("press-list-sync")
    check("press sync card exists", bool(press))
    check("press sync flags sheet gap", "Major Outlet" in press)

    sourcing = card("partnership-sourcing")
    check("sourcing card exists", bool(sourcing))
    check("sourcing lists new target", "Target Alpha" in sourcing or "example-alpha" in sourcing)
    check("sourcing excludes contacted", "Target Closed" not in sourcing or "contacted" not in sourcing.lower())

    tasks = card("slack-task-tracking")
    check("task-tracker card exists", bool(tasks))
    check("task-tracker flags overdue", "OVERDUE" in tasks)
    check("task-tracker shows owner", "deal-lead" in tasks or "recruiting-lead" in tasks)
    check("task-tracker excludes done", "Publish Q2 press update" not in tasks)

    check("no draft content in watch cards", "STATUS: DRAFT" not in all_cards)

    if FAILURES:
        print(f"\nFAILED {len(FAILURES)} checks:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("\nPASS - all use-case playbooks produce correct cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
