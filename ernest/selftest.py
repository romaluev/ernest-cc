"""Sandboxed smoke canary: prove the engine works end-to-end, without side effects.

Copies the current profile's `data/` + `memory/` into a throwaway sandbox and
runs the real CLI (watch -> brief -> grade) there, plus the gate selftest.
Assertions are structural (commands exit 0, artifacts appear) rather than
content-specific, so the canary passes on any profile — sample or personalized.

Used by: `ernest selftest` (manual), `ernest heal` (verify after repairs), and
`ernest update` (block promotion of a build that can't run its own daily loop —
the same promotion-gate idea as scripts/self-update.sh's gate check).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple

from .config import Config

_PKG_ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: List[str], env: dict, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "ernest.cli", *cmd],
                          capture_output=True, text=True, env=env, cwd=str(cwd),
                          timeout=120)


def run(cfg: Config, today: str = "") -> Tuple[bool, List[str]]:
    """Returns (ok, report_lines). Never touches the real profile."""
    report: List[str] = []
    ok = True

    def check(label: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        report.append(f"  [{'ok ' if cond else 'FAIL'}] {label}" + (f" — {detail}" if detail and not cond else ""))
        ok = ok and cond

    # Gate selftest in-process first — if the guardrail is broken, stop loudly.
    try:
        from . import gate
        check("gate selftest (draft-first guardrail)", gate.selftest() == 0)
    except Exception as exc:  # noqa: BLE001
        check("gate selftest (draft-first guardrail)", False, str(exc))

    with tempfile.TemporaryDirectory(prefix="ernest-selftest-") as tmp:
        sandbox = Path(tmp)
        profile = sandbox / "profile"
        profile.mkdir()
        for sub in ("data", "memory"):
            src = getattr(cfg, f"{sub}_dir")
            if src.is_dir():
                shutil.copytree(src, profile / sub)
        env = dict(os.environ)
        env.update({
            "ERNEST_PROFILE_DIR": str(profile),
            "ERNEST_LOCAL_VAULT": str(sandbox / "vault"),
            "ERNEST_MODE": "local",
            "ERNEST_NO_RENDER": "1",
            "PYTHONPATH": str(_PKG_ROOT),
        })
        if today:
            env["ERNEST_TODAY"] = today
        env.pop("ERNEST_BRAIN_URL", None)

        proc = _run(["watch"], env, _PKG_ROOT)
        check("`ernest watch` exits 0", proc.returncode == 0, proc.stderr.strip()[:200])

        proc = _run(["brief"], env, _PKG_ROOT)
        check("`ernest brief` exits 0", proc.returncode == 0, proc.stderr.strip()[:200])
        daily = sandbox / "vault" / "Ernest" / "00-Daily"
        briefs = list(daily.glob("brief--*.md")) if daily.is_dir() else []
        check("brief file written", bool(briefs))
        if briefs:
            check("brief has content", briefs[0].stat().st_size > 40)

        proc = _run(["grade"], env, _PKG_ROOT)
        check("`ernest grade` exits 0", proc.returncode == 0, proc.stderr.strip()[:200])

        proc = _run(["doctor"], env, _PKG_ROOT)
        # Sandbox doctor may exit 1 only if the copied profile is itself broken —
        # that is a real finding, surface it.
        check("`ernest doctor` exits 0 in sandbox", proc.returncode == 0,
              (proc.stdout + proc.stderr).strip()[-200:])

    return ok, report
