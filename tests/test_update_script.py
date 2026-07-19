#!/usr/bin/env python3
"""Offline checks for the self-update path (scripts/self-update.sh + launcher).

No network: a local bare repo stands in for GitHub. Covers the failure modes
found in live testing 2026-07-19:
  1. a profile pinned to a channel branch that no longer exists on origin
     (pre-1.2 installs pinned to 'stable') must fall back to main, not strand;
  2. after a rollback, apply must refuse to retry until the flag is cleared;
  3. the generated launcher must cd to the profile so `python3 -m ernest.cli`
     can never import an `ernest` package from the caller's cwd (hijack);
  4. the update script must stay parseable and keep resolve_channel wired
     into check/apply/status.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "self-update.sh"

FAILURES = []


def check(label: str, ok: bool) -> None:
    print(("ok  " if ok else "FAIL") + " " + label)
    if not ok:
        FAILURES.append(label)


def run(cmd, **kw):
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    return subprocess.run(cmd, **kw)


def git(*args, cwd):
    return run(["git", "-C", str(cwd), *args])


def main() -> int:
    # -- 4. static guards ---------------------------------------------------
    check("self-update.sh parses (bash -n)",
          run(["bash", "-n", str(SCRIPT)]).returncode == 0)
    text = SCRIPT.read_text()
    check("resolve_channel defined", "resolve_channel()" in text)
    check("resolve_channel wired into check/apply/status",
          text.count("resolve_channel || true") >= 3)
    installer = (ROOT / "install.sh").read_text()
    check("launcher cds to profile before exec (cwd-hijack guard)",
          re.search(r"cd \"\$PROFILE_DIR\"\nexec python3 -m ernest\.cli", installer)
          is not None)

    with tempfile.TemporaryDirectory(prefix="ernest-upd.") as td:
        tmp = Path(td)
        env = dict(os.environ)

        # A local "GitHub": bare origin with a main branch and one extra commit.
        origin = tmp / "origin.git"
        seed = tmp / "seed"
        seed.mkdir()
        (seed / "marker.txt").write_text("v1\n")
        # A minimal tree the validator will accept is overkill here; instead we
        # exercise only the fetch/branch mechanics, so validation never runs
        # (old == new after fallback).
        git("init", "-q", "-b", "main", cwd=seed)
        git("add", "-A", cwd=seed)
        git("-c", "user.email=t@t", "-c", "user.name=t",
            "commit", "-qm", "seed", cwd=seed)
        run(["git", "clone", "-q", "--bare", str(seed), str(origin)])

        src = tmp / "src"
        run(["git", "clone", "-q", str(origin), str(src)])
        profile = tmp / "profile"
        (profile / "logs").mkdir(parents=True)

        base_env = {
            **env,
            "ERNEST_SRC_DIR": str(src),
            "ERNEST_PROFILE_DIR": str(profile),
            "ERNEST_LOCAL_VAULT": str(tmp / "vault"),
        }

        # -- 1. dead-channel fallback --------------------------------------
        r = run(["bash", str(SCRIPT), "check"],
                env={**base_env, "ERNEST_UPDATE_CHANNEL": "retired"})
        log = (profile / "logs" / "selfupdate.log").read_text()
        check("dead channel: check exits 0", r.returncode == 0)
        check("dead channel: fallback logged",
              "missing on origin — falling back to main" in log)
        check("dead channel: ends up-to-date on main", "up-to-date" in log)

        # -- 2. rollback flag blocks apply ---------------------------------
        (profile / "logs" / "update-rolledback.flag").write_text("test\n")
        r = run(["bash", str(SCRIPT), "apply"], env=base_env)
        check("rollback flag: apply blocked with exit 4", r.returncode == 4)
        (profile / "logs" / "update-rolledback.flag").unlink()

        # -- 3. status never mutates ---------------------------------------
        head_before = git("rev-parse", "HEAD", cwd=src).stdout.strip()
        run(["bash", str(SCRIPT), "status"], env=base_env)
        head_after = git("rev-parse", "HEAD", cwd=src).stdout.strip()
        check("status leaves HEAD untouched", head_before == head_after)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} failure(s)")
        return 1
    print("all update-script checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
