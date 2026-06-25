#!/usr/bin/env python3
"""End-to-end lifecycle test for the Ernest engine.

Drives the real CLI through the whole flow on local data, with no VPS, no live
connectors, and no model: doctor -> onboard -> watch -> brief -> draft ->
new-automation -> learn. Every step asserts a real artifact, not a log line.
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


def run(profile: Path, vault: Path, *args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.update({
        "ERNEST_PROFILE_DIR": str(profile),
        "ERNEST_LOCAL_VAULT": str(vault),
        "ERNEST_LOCAL_MEMORY_FILE": str(vault / "memory.json"),
        "ERNEST_MODE": "local",
        "ERNEST_TODAY": "2026-06-25",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    return subprocess.run(
        [sys.executable, "-m", "ernest.cli", *args],
        cwd=str(ROOT), env=env, text=True, capture_output=True, check=False,
    )


def main() -> int:
    profile = Path(tempfile.mkdtemp(prefix="ernest_e2e_profile_"))
    vault = Path(tempfile.mkdtemp(prefix="ernest_e2e_vault_"))

    # Mimic an installed profile: engine reads memory/ and data/ from the profile.
    shutil.copytree(ROOT / "memory", profile / "memory")
    shutil.copytree(ROOT / "data", profile / "data")
    (profile / "logs").mkdir(exist_ok=True)

    doctor = run(profile, vault, "doctor")
    check("doctor exits 0", doctor.returncode == 0)
    check("doctor reports health", "Ernest health check: ok" in doctor.stdout)
    check("doctor reports local mode", "mode: local" in doctor.stdout.lower())

    onboard = run(profile, vault, "onboard", "--name", "Sam Director",
                  "--role", "CEO", "--company", "UnicornCo", "--non-interactive")
    check("onboard exits 0", onboard.returncode == 0)
    check("onboard wrote company",
          "UnicornCo" in (profile / "memory" / "company-core.md").read_text())
    check("onboard marker written", (vault / ".onboarded").exists())

    watch = run(profile, vault, "watch")
    check("watch exits 0", watch.returncode == 0)
    watch_dir = vault / "Ernest" / "00-Watch"
    cards = list(watch_dir.glob("*.md")) if watch_dir.exists() else []
    check("watch wrote at least one card", len(cards) >= 1)
    card_text = "\n".join(c.read_text() for c in cards)
    check("dropped follow-up detects ExampleCo", "ExampleCo" in card_text)
    check("watch never drafts in cards", "STATUS: DRAFT" not in card_text)

    brief = run(profile, vault, "brief")
    check("brief exits 0", brief.returncode == 0)
    check("brief mentions a follow-up",
          "follow-up" in brief.stdout.lower() or "follow up" in brief.stdout.lower())
    daily_dir = vault / "Ernest" / "00-Daily"
    check("brief file written",
          daily_dir.exists() and len(list(daily_dir.glob("*.md"))) >= 1)

    draft = run(profile, vault, "draft", "--concern", "dropped-followups")
    check("draft exits 0", draft.returncode == 0)
    drafts_dir = vault / "Ernest" / "00-Drafts"
    draft_files = list(drafts_dir.glob("*.md")) if drafts_dir.exists() else []
    check("draft file written", len(draft_files) >= 1)
    draft_text = "\n".join(f.read_text() for f in draft_files)
    check("draft is labeled draft-only", "STATUS: DRAFT" in draft_text)
    check("draft labels local-export source", "local-export" in draft_text)
    check("draft references ExampleCo", "ExampleCo" in draft_text)

    add = run(profile, vault, "new-automation", "--id", "investor-followups",
              "--playbook", "account-followup-recovery",
              "--description", "Watch investor threads weekly", "--staleness", "5d")
    check("new-automation exits 0", add.returncode == 0)
    concerns = (profile / "memory" / "standing-concerns.md").read_text()
    check("new concern registered", "investor-followups" in concerns)
    check("new skill scaffolded",
          (profile / "skills" / "investor-followups" / "SKILL.md").exists())

    learn = run(profile, vault, "learn", "--note",
                "CEO keeps manually checking partner renewals every Monday.")
    check("learn exits 0", learn.returncode == 0)
    summary = profile / "logs" / "learning-summary.md"
    check("learn wrote a proposal summary", summary.exists())
    if summary.exists():
        text = summary.read_text()
        check("proposal is proposal-only", "status: proposed" in text.lower())
        check("proposal needs approval", "approval" in text.lower())

    if FAILURES:
        print(f"\nFAILED {len(FAILURES)} checks:")
        for failure in FAILURES:
            print(f"  - {failure}")
        print("\n--- last stderr (learn) ---")
        print(learn.stderr)
        return 1
    print("\nPASS - Ernest e2e lifecycle works on local data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
