#!/usr/bin/env python3
"""Living preferences: engine honors them; feedback is logged."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FAILURES: list[str] = []


def check(label: str, condition: bool) -> None:
    print(f"  [{'ok  ' if condition else 'FAIL'}] {label}")
    if not condition:
        FAILURES.append(label)


def main() -> int:
    from ernest.config import load
    from ernest.preferences import load as load_prefs, truthy

    profile = Path(tempfile.mkdtemp(prefix="ernest_prefs_profile_"))
    vault = Path(tempfile.mkdtemp(prefix="ernest_prefs_vault_"))
    shutil.copytree(ROOT / "memory", profile / "memory")
    shutil.copytree(ROOT / "data", profile / "data")

    env = os.environ.copy()
    env.update({
        "ERNEST_PROFILE_DIR": str(profile),
        "ERNEST_LOCAL_VAULT": str(vault),
        "ERNEST_MODE": "local",
        "ERNEST_TODAY": "2026-06-25",
        "ERNEST_NO_OPEN": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    })

    def run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "ernest.cli", *args],
            cwd=str(ROOT), env=env, text=True, capture_output=True, check=False)

    # Defaults parse from the shipped preferences.md.
    os.environ["ERNEST_PROFILE_DIR"] = str(profile)
    os.environ["ERNEST_LOCAL_VAULT"] = str(vault)
    prefs = load_prefs(load())
    check("auto_render defaults on", truthy(prefs.get("auto_render", "on")))
    check("max_key_points present", prefs.get("max_key_points") == "6")

    digest = vault / "Ernest" / "00-Daily" / "digest--2026-06-25.html"

    # auto_render on -> start writes a digest and mentions read more.
    start_on = run("start")
    check("start (render on) exits 0", start_on.returncode == 0)
    check("start mentions read more", "Read more" in start_on.stdout)
    check("digest written when on", digest.exists())

    # Flip to off -> start neither writes nor advertises a digest.
    if digest.exists():
        digest.unlink()
    pref_file = profile / "memory" / "preferences.md"
    pref_file.write_text(
        pref_file.read_text(encoding="utf-8").replace("auto_render: on", "auto_render: off"),
        encoding="utf-8")
    start_off = run("start")
    check("start (render off) exits 0", start_off.returncode == 0)
    check("no read-more line when off", "Read more" not in start_off.stdout)
    check("no digest when off", not digest.exists())

    # Feedback is recorded as a JSON line.
    fb = run("feedback", "too", "long", "4", "bullets")
    check("feedback exits 0", fb.returncode == 0)
    log = profile / "logs" / "feedback.jsonl"
    check("feedback log written", log.exists())
    if log.exists():
        last = [l for l in log.read_text(encoding="utf-8").splitlines() if l.strip()][-1]
        entry = json.loads(last)
        check("feedback note captured", entry.get("note") == "too long 4 bullets")

    if FAILURES:
        print("FAILED preferences tests:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("PASS - preferences gate + feedback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
