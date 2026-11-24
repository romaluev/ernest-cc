#!/usr/bin/env python3
"""Blocker 3 — malformed concern config must FAIL LOUD, not silently disable reminders."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ernest import concerns, config  # noqa: E402

FAILURES: list[str] = []


def check(label: str, cond: bool) -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label}")
    if not cond:
        FAILURES.append(label)


def _cfg(tmp: Path) -> config.Config:
    os.environ["ERNEST_PROFILE_DIR"] = str(tmp)
    os.environ["ERNEST_LOCAL_VAULT"] = str(tmp / "vault")
    (tmp / "memory").mkdir(parents=True, exist_ok=True)
    return config.load()


VALID = "# Concerns\n```yaml\nconcerns:\n  - id: dropped-followup\n    playbook: account-followup-recovery\n    enabled: true\n```\n"
ALL_DISABLED = "```yaml\nconcerns:\n  - id: x\n    playbook: p\n    enabled: false\n```\n"
NO_FENCE = "# My concerns\n\n- id: dropped-followup\n  playbook: account-followup-recovery\n  enabled: true\n(this should have been inside a yaml fence but isn't)\n"
GARBAGE_FENCE = "```yaml\nthis: is not a concerns list\nrandom junk here\nmore: stuff\n```\n"
EMPTY = "# Concerns\n\n(none yet)\n"


def run_case(name: str, content: str | None, expect_level: str) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="ernest_conc_"))
    cfg = _cfg(tmp)
    if content is not None:
        cfg.concerns_file.write_text(content, encoding="utf-8")
    st = concerns.status(cfg)
    check(f"{name}: level == {expect_level} (got {st.level}: {st.message[:50]})", st.level == expect_level)


def test_all() -> None:
    run_case("valid", VALID, "ok")
    run_case("all-disabled", ALL_DISABLED, "error")
    run_case("content-but-no-fence", NO_FENCE, "error")
    run_case("garbage-fence", GARBAGE_FENCE, "error")
    run_case("missing-file", None, "warn")
    run_case("legitimately-empty", EMPTY, "warn")

    # doctor must report degraded + return 1 on a malformed file
    tmp = Path(tempfile.mkdtemp(prefix="ernest_doc_"))
    cfg = _cfg(tmp)
    for f in ("company-core.md", "ceo-persona.md", "standing-concerns.md"):
        (cfg.memory_dir / f).write_text(NO_FENCE if f == "standing-concerns.md" else "x", encoding="utf-8")
    from ernest import cli
    import argparse
    rc = cli.cmd_doctor(cfg, argparse.Namespace())
    check("doctor returns 1 on malformed concerns (not silent ok)", rc == 1)


if __name__ == "__main__":
    test_all()
    if FAILURES:
        print(f"FAILED {len(FAILURES)}:")
        for f in FAILURES:
            print("  -", f)
        raise SystemExit(1)
    print("PASS - concern config fails loud when malformed")
