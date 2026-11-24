#!/usr/bin/env python3
"""Full thread reading: parse, cache, slack + email."""
from __future__ import annotations

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
    from ernest.read_threads import run as read_run
    from ernest.sources import load_threads
    from ernest.thread_reader import load_one, parse_markdown

    sample = ROOT / "data" / "mail" / "sample-thread.md"
    conv = parse_markdown(sample)
    check("parses email thread messages", conv is not None and conv.message_count >= 3)
    check("detects last inbound body", "proposal" in (conv.last_inbound().body.lower() if conv else ""))

    slack = ROOT / "data" / "slack" / "threads" / "slack-partnership-deck.md"
    sconv = parse_markdown(slack)
    check("parses slack thread", sconv is not None and sconv.channel == "slack")

    profile = Path(tempfile.mkdtemp(prefix="ernest_threads_"))
    vault = Path(tempfile.mkdtemp(prefix="ernest_threads_vault_"))
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

    proc = subprocess.run(
        [sys.executable, "-m", "ernest.cli", "read", "--thread", "sample-thread"],
        cwd=str(ROOT), env=env, text=True, capture_output=True, check=False,
    )
    check("ernest read exits 0", proc.returncode == 0)

    cached = vault / "Ernest" / "00-Threads" / "sample-thread.md"
    check("thread cached to vault", cached.is_file())
    if cached.is_file():
        text = cached.read_text(encoding="utf-8")
        check("cache includes message bodies", "Gentle bump" in text)

    os.environ.update(env)
    cfg = load()
    threads = load_threads(cfg)
    slack_threads = [t for t in threads if t.category == "slack"]
    check("load_threads includes slack", any(t.id == "slack-partnership-deck" for t in slack_threads))

    paths = read_run(cfg, owed_only=True)
    check("read --owed caches multiple", len(paths) >= 1)

    if FAILURES:
        print("FAILED thread tests:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("PASS - full thread reading")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
