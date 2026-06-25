#!/usr/bin/env python3
"""Verify the CEO's real use-cases produce correct remind/assign cards.

These are the concrete automations the CEO asked for, all over email and all
"no drafts, just assign/remind":

  1. Add Manoj to B2B threads he is missing from.
  2. Find B2B marketing/sales candidates needing follow-up (assign Alua/Limon).
  3. Surface important contacts where a follow-up slipped (Nubank-style).
  4. Sync email contacts against a HubSpot list (South Korea / Alvin).
  5. Sync email contacts against a Google Sheet export (Press / TechCrunch).
  6. Manage a sourcing pipeline of partnership/hire targets.

The engine runs on the bundled sample data with no model and no connectors.
"""
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

    # 1. Add Manoj to B2B threads
    manoj = card("add-manoj-to-b2b")
    check("add-manoj card exists", bool(manoj))
    check("add-manoj names Manoj", "Manoj" in manoj)
    check("add-manoj flags the B2B intro missing him", "BridgeAI" in manoj)
    check("add-manoj excludes thread already having Manoj", "Skyline" not in manoj)

    # 2. Candidate reach-out (Alua / Limon)
    cand = card("b2b-candidates")
    check("candidate card exists", bool(cand))
    check("candidate flags Dana Kim", "Dana Kim" in cand)
    check("candidate assigns Alua/Limon", "Alua" in cand or "Limon" in cand)

    # 3. Important contact follow-up slipped (Nubank)
    important = card("important-followups")
    check("important-followups card exists", bool(important))
    check("important-followups surfaces Nubank", "Nubank" in important)

    # 4. South Korea: email vs Alvin's HubSpot list
    korea = card("korea-list-sync")
    check("korea sync card exists", bool(korea))
    check("korea sync flags SeoulTech missing from list", "SeoulTech" in korea)

    # 5. Press list vs Google Sheet export
    press = card("press-list-sync")
    check("press sync card exists", bool(press))
    check("press sync flags TechCrunch missing from sheet", "TechCrunch" in press)

    # 6. Sourcing pipeline
    sourcing = card("partnership-sourcing")
    check("sourcing card exists", bool(sourcing))
    check("sourcing lists a new ex-Skolkovo target", "anda-gansca" in sourcing or "Anda" in sourcing)
    check("sourcing excludes already-contacted targets", "already reached" not in sourcing)

    # 7. Slack task tracking (first step: open/overdue by owner)
    tasks = card("slack-task-tracking")
    check("task-tracker card exists", bool(tasks))
    check("task-tracker flags an overdue task", "OVERDUE" in tasks)
    check("task-tracker shows an owner", "Manoj" in tasks or "Alua" in tasks)
    check("task-tracker excludes done tasks", "Publish Q2 press update" not in tasks)

    # Global guarantee: these are remind/assign only, never drafts.
    check("no draft content in any watch card", "STATUS: DRAFT" not in all_cards)

    if FAILURES:
        print(f"\nFAILED {len(FAILURES)} checks:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("\nPASS - all CEO use-case playbooks produce correct cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
