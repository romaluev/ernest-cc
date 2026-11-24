#!/usr/bin/env python3
"""End-to-end: the two surfaces cooperate over ONE shared state.

1. Standalone install works with NO VPS / NO network (the laptop is complete).
2. The brain (the VPS surface) writes a watch card + memory into the SAME vault
   and memory dir the local engine reads — so a card filed by the 24/7 VPS shows
   up for the laptop, and vice versa. This is the synchronization guarantee.
"""
from __future__ import annotations

import json
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


def test_two_surfaces_share_state() -> None:
    sb = Path(tempfile.mkdtemp(prefix="ernest_coop_"))
    profile, vault = sb / "profile", sb / "vault"
    try:
        # 1. Standalone install (default local mode, no brain URL/token).
        env = dict(os.environ)
        env.update({"ERNEST_PROFILE_DIR": str(profile), "ERNEST_LOCAL_VAULT": str(vault)})
        env.pop("ERNEST_BRAIN_URL", None)
        env.pop("ERNEST_BRAIN_TOKEN", None)
        inst = subprocess.run(["bash", str(ROOT / "install.sh"), "--no-run"],
                              cwd=str(ROOT), env=env, text=True, capture_output=True, check=False)
        check("standalone install ok", inst.returncode == 0)
        if inst.returncode != 0:
            print(inst.stderr); return

        # local .mcp.json must NOT reference any brain (true standalone)
        mcp = json.loads((profile / ".mcp.json").read_text(encoding="utf-8"))
        check("standalone has no brain MCP", "ernest-brain" not in json.dumps(mcp))

        # engine runs with no network/model
        env2 = dict(env)
        env2["PYTHONPATH"] = str(profile)
        start = subprocess.run([sys.executable, "-m", "ernest.cli", "start"],
                               cwd=str(profile), env=env2, text=True, capture_output=True, check=False)
        check("ernest start runs offline", start.returncode == 0)

        # 2. Brain (VPS surface) writes into the SAME profile/vault.
        sys.path.insert(0, str(ROOT))
        os.environ["ERNEST_PROFILE_DIR"] = str(profile)
        os.environ["ERNEST_LOCAL_VAULT"] = str(vault)
        from ernest import config
        from brain.brain_core import Brain
        brain = Brain(config.load())

        r = brain.call("write_watch_card", {"concern_id": "vip-recovery",
                       "source_ref": "mail/xyz", "due_date": "2026-07-01", "body": "VIP went quiet"})
        check("brain writes a watch card", r.get("ok") is True)

        # the card lands in the SAME vault the local engine uses
        watch_dir = vault / "Ernest" / "00-Watch"
        cards = list(watch_dir.glob("card-*.md")) if watch_dir.is_dir() else []
        check("card visible in the shared local vault", len(cards) == 1)

        # brain memory write lands in the shared memory dir
        brain.call("write_memory", {"text": "Brain note from the VPS", "scope": "ops"})
        s = brain.call("search_memory", {"query": "brain note"})
        check("brain memory readable via shared store", s["count"] >= 1)
        check("brain memory file in profile/memory",
              (profile / "memory" / "brain-memory.jsonl").is_file())

        # the brain enforces the SAME gate (a mutating connector action is refused)
        blocked = brain.call("create_mail_draft", {"to": "a@b.com", "subject": "x", "body": "y"})
        check("brain create_mail_draft stays a draft (no send)", blocked.get("state") == "draft")
    finally:
        shutil.rmtree(sb, ignore_errors=True)


if __name__ == "__main__":
    test_two_surfaces_share_state()
    if FAILURES:
        print(f"FAILED {len(FAILURES)} checks:")
        for failure in FAILURES:
            print(f"  - {failure}")
        raise SystemExit(1)
    print("PASS - cooperation: standalone-first + brain share one state")
