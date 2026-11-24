#!/usr/bin/env python3
"""Blocker 4 — onboarding + reinstall must never destroy the CEO's memory."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ernest import config, onboard  # noqa: E402

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


def test_reonboard_preserves_memory() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="ernest_mem_"))
    cfg = _cfg(tmp)
    onboard.run(cfg, onboard.Answers(name="Alex", company="Northwind", icp="AI creators",
                                     redlines="never email investors"))
    core = cfg.memory_dir / "company-core.md"
    # CEO hand-adds a custom bullet
    core.write_text(core.read_text(encoding="utf-8") + "- Board cadence: monthly\n", encoding="utf-8")

    # local-first defaults (no hardcoded HubSpot/VPS)
    txt = core.read_text(encoding="utf-8")
    check("default CRM is local-first (not hardcoded HubSpot)", "CRM: none" in txt and "HubSpot (canonical)" not in txt)
    check("memory stays local by default", "stays on this machine" in txt)

    # re-onboard with DIFFERENT answers
    onboard.run(cfg, onboard.Answers(name="Alex M", company="Northwind Inc", icp="studios",
                                     redlines="never email press"))
    after = core.read_text(encoding="utf-8")
    check("original company preserved (not overwritten)", "Northwind" in after)
    check("custom bullet preserved across re-onboard", "Board cadence: monthly" in after)
    check("a backup was written", any((cfg.memory_dir / ".backups").glob("*/company-core.md")))


def test_plain_reinstall_does_not_clobber_memory() -> None:
    sb = Path(tempfile.mkdtemp(prefix="ernest_reinst_"))
    profile, vault = sb / "p", sb / "v"
    env = dict(os.environ)
    env.update({"ERNEST_PROFILE_DIR": str(profile), "ERNEST_LOCAL_VAULT": str(vault)})
    r1 = subprocess.run(["bash", str(ROOT / "install.sh"), "--no-run"], cwd=str(ROOT),
                        env=env, text=True, capture_output=True, check=False)
    check("first install ok", r1.returncode == 0)
    mem = profile / "memory" / "company-core.md"
    mem.write_text(mem.read_text(encoding="utf-8") + "\nCEO HAND EDIT\n", encoding="utf-8")
    # plain re-run of ./install.sh (NOT --refresh)
    r2 = subprocess.run(["bash", str(ROOT / "install.sh"), "--no-run"], cwd=str(ROOT),
                        env=env, text=True, capture_output=True, check=False)
    check("re-install ok", r2.returncode == 0)
    check("memory edit survives plain re-install", "CEO HAND EDIT" in mem.read_text(encoding="utf-8"))


def test_first_onboarding_overwrites_sample_identity() -> None:
    """First onboarding must REPLACE the shipped sample identity (e.g. 'Northwind'),
    not merge-preserve it — so a real user never sees placeholder names."""
    tmp = Path(tempfile.mkdtemp(prefix="ernest_seed_"))
    cfg = _cfg(tmp)
    # Simulate the shipped SAMPLE seed (what install.sh copies), no .onboarded marker.
    (cfg.memory_dir / "company-core.md").write_text(
        "# Company Core\n\n- Company: Northwind\n- ICP: AI video creators\n", encoding="utf-8")
    (cfg.memory_dir / "ceo-persona.md").write_text(
        "# CEO Persona\n\n- Name: Sam Rivera\n- Company: Northwind\n", encoding="utf-8")
    # First onboarding with the REAL identity.
    onboard.run(cfg, onboard.Answers(name="Real Person", company="RealCo Inc", icp="studios"))
    core = (cfg.memory_dir / "company-core.md").read_text(encoding="utf-8")
    persona = (cfg.memory_dir / "ceo-persona.md").read_text(encoding="utf-8")
    check("sample company replaced by real one", "RealCo Inc" in core and "Northwind" not in core)
    check("sample persona name replaced", "Real Person" in persona and "Sam Rivera" not in persona)


if __name__ == "__main__":
    test_reonboard_preserves_memory()
    test_first_onboarding_overwrites_sample_identity()
    test_plain_reinstall_does_not_clobber_memory()
    if FAILURES:
        print(f"FAILED {len(FAILURES)}:")
        for f in FAILURES:
            print("  -", f)
        raise SystemExit(1)
    print("PASS - memory-safe onboarding + reinstall")
