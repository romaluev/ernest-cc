#!/usr/bin/env python3
"""Deep audit manifest and window filtering."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FAILURES: list[str] = []


def check(label: str, condition: bool) -> None:
    print(f"  [{'ok  ' if condition else 'FAIL'}] {label}")
    if not condition:
        FAILURES.append(label)


def main() -> int:
    from ernest.audit import build_chunks, run_local
    from ernest.config import load

    chunks = build_chunks(date(2026, 6, 25), 365, 30)
    check("365d window yields multiple chunks", len(chunks) >= 12)
    check("newest chunk ends today", chunks[0].end == date(2026, 6, 25))

    profile = Path(tempfile.mkdtemp(prefix="ernest_audit_profile_"))
    vault = Path(tempfile.mkdtemp(prefix="ernest_audit_vault_"))
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
        [sys.executable, "-m", "ernest.cli", "audit", "--window", "365d"],
        cwd=str(ROOT), env=env, text=True, capture_output=True, check=False,
    )
    check("audit exits 0", proc.returncode == 0)
    if proc.returncode != 0:
        print(proc.stderr)

    watch_dir = vault / "Ernest" / "00-Watch"
    manifests = list(watch_dir.glob("audit-manifest--*.md")) if watch_dir.exists() else []
    check("audit manifest written", bool(manifests))
    if manifests:
        text = manifests[0].read_text(encoding="utf-8")
        check("manifest forbids mid-audit stop", "Do **not** stop" in text)
        check("manifest lists chunks", "chunk 1:" in text)

    cfg = load()
    items, _ = run_local(cfg, window_days=7, staleness_days=1)
    all_items, _ = run_local(cfg, window_days=365, staleness_days=1)
    check("narrow window can exclude older threads", len(items) <= len(all_items))

    # Cold-start -> incremental window logic (FRESH profile: the subprocess audit
    # above already recorded a sweep in `profile`, so use a new dir to test cold-start).
    from ernest.audit import resolve_window_days, record_sweep, read_last_sweep, COLD_START_DAYS
    fresh = Path(tempfile.mkdtemp(prefix="ernest_sweep_"))
    os.environ["ERNEST_PROFILE_DIR"] = str(fresh)
    os.environ["ERNEST_LOCAL_VAULT"] = str(fresh / "vault")
    iso = load()
    wd, cold = resolve_window_days(iso, "")
    check("first sweep is cold-start (12 months)", cold and wd == COLD_START_DAYS)
    wd2, cold2 = resolve_window_days(iso, "90d")
    check("explicit window overrides cold-start", not cold2 and wd2 == 90)
    record_sweep(iso)
    check("sweep recorded", read_last_sweep(iso) == iso.today)
    wd3, cold3 = resolve_window_days(iso, "")
    check("after a sweep, window is incremental (not cold-start)", (not cold3) and wd3 < COLD_START_DAYS)

    if FAILURES:
        print("FAILED audit tests:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("PASS - audit manifest and window filtering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
