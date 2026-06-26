#!/usr/bin/env python3
"""ICP grading: B2B tiers, talent tiers, hard filter, and graded cards."""
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


def test_b2b() -> None:
    from ernest.grading import grade_b2b

    # CRM tier wins, high confidence.
    g = grade_b2b(company="Apex Bank", crm_tier="vip")
    check("CRM vip -> tier-1", g.tier == "tier-1" and g.confidence == "high")

    # ICP category + enterprise intent.
    g = grade_b2b(company="Brightline Creative",
                  text="creative ad agency wants enterprise rollout and MSA",
                  category="b2b")
    check("ad agency + enterprise -> tier-1", g.tier == "tier-1")

    # Provider list hit.
    g = grade_b2b(company="OpenAI", text="exploring a collaboration")
    check("model provider -> tier-1", g.tier == "tier-1")

    # Prior contact with Alex.
    g = grade_b2b(company="Unknown Co", text="great speaking, as discussed with Alex")
    check("prior contact w/ Alex -> tier-1", g.tier == "tier-1")

    # Cold vendor pitch -> trash.
    g = grade_b2b(company="GrowthHooks",
                  text="we offer SEO services and backlinks to boost your traffic")
    check("vendor pitch -> trash", g.tier == "trash")

    # Unknown company, no signal -> tier-2 low + flag.
    g = grade_b2b(company="Mystery LLC", text="hello, we'd like to chat")
    check("unknown -> tier-2 low", g.tier == "tier-2" and g.confidence == "low")
    check("unknown is flagged for review", bool(g.flags))

    # Large fund.
    g = grade_b2b(company="Big Capital", text="fund interested", fund_aum_busd=5.0)
    check("large fund -> tier-1", g.tier == "tier-1")


def test_talent() -> None:
    from ernest.grading import grade_talent

    # Senior Big Tech + AI media -> tier-1 high.
    g = grade_talent(name="Dmitry", company="Google", title="Engineering Lead",
                     profile="machine learning, generative video, in the United States")
    check("senior big tech + ai media -> tier-1", g.tier == "tier-1")
    check("strong structural signal -> high confidence", g.confidence == "high")

    # PM at big tech in US (no senior title, no tech, no ai media) -> tier-2, NOT tier-1.
    g = grade_talent(name="Marina", company="Stripe", title="Product Manager",
                     profile="product manager, go-to-market, US startup experience")
    check("PM in tier-1 country is NOT tier-1", g.tier == "tier-2")

    # Hard filter: current Northwind -> tier-3.
    g = grade_talent(name="Insider", company="Northwind", profile="works at Northwind")
    check("current Northwind -> tier-3 (excluded)", g.tier == "tier-3")

    # Investor exclusion.
    g = grade_talent(name="Backer", profile="angel who invested in Northwind")
    check("Northwind investor -> tier-3 (excluded)", g.tier == "tier-3")

    # Thin profile -> tier-3 low, flagged.
    g = grade_talent(name="Nobody", profile="analyst at a local company")
    check("thin profile -> tier-3 low", g.tier == "tier-3" and g.confidence == "low")
    check("thin profile flagged", bool(g.flags))


def test_scoring_breadth_and_sorting() -> None:
    """The team's complaint: too narrow, too few, badly sorted. Verify the fixes."""
    from ernest.grading import grade_b2b, grade_talent

    # Density: more signals -> higher score (so it ranks first within a tier).
    strong = grade_b2b(company="NVIDIA", text="enterprise rollout, contract, RFP", category="ai studio")
    weakish = grade_b2b(company="OpenAI", text="exploring a collaboration")
    check("multi-signal lead outscores single-signal", strong.score > weakish.score)
    check("both still tier-1", strong.tier == "tier-1" and weakish.tier == "tier-1")

    # Abbreviation matching: 'Sr. ML Engineer' should resolve like senior + machine learning.
    g = grade_talent(name="X", company="Google", title="Sr. ML Engineer",
                     profile="text-to-video research, US")
    check("abbrev 'Sr. ML' surfaces as tier-1", g.tier == "tier-1" and g.score > 0)

    # Breadth: a broadened big-tech name (DeepMind) now surfaces instead of vanishing.
    g = grade_talent(name="Y", company="DeepMind", title="Research Scientist",
                     profile="diffusion models")
    check("broadened company (DeepMind) surfaces (not tier-3)", g.tier in ("tier-1", "tier-2"))

    # Sorting: within tier-2, denser profile scores higher.
    a = grade_talent(name="A", company="Stripe", title="Product Manager",
                     profile="go-to-market, growth, US startup, series b")
    b = grade_talent(name="B", company="SomeCo", title="Product Manager", profile="product manager")
    check("denser tier-2 profile scores higher (better sort)",
          a.tier == "tier-2" and b.tier in ("tier-2", "tier-3") and a.score > b.score)


def test_cards() -> None:
    profile = Path(tempfile.mkdtemp(prefix="ernest_grade_"))
    vault = Path(tempfile.mkdtemp(prefix="ernest_grade_vault_"))
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
    proc = subprocess.run([sys.executable, "-m", "ernest.cli", "grade"],
                          cwd=str(ROOT), env=env, text=True, capture_output=True, check=False)
    check("grade exits 0", proc.returncode == 0)
    watch_dir = vault / "Ernest" / "00-Watch"
    b2b = next(watch_dir.glob("b2b-grades--*.md"), None)
    talent = next(watch_dir.glob("talent-grades--*.md"), None)
    check("b2b grade card written", b2b is not None)
    check("talent grade card written", talent is not None)
    if b2b:
        text = b2b.read_text()
        check("b2b card has a TIER-1", "[TIER-1]" in text)
        check("b2b card flags trash vendor", "[TRASH]" in text)
        # Tier-1 must appear before Trash (sorted).
        check("sorted tier-1 before trash", text.index("[TIER-1]") < text.index("[TRASH]"))
    if talent:
        ttext = talent.read_text()
        check("talent card has a TIER-1", "[TIER-1]" in ttext)
        check("talent card has a TIER-3", "[TIER-3]" in ttext)

    # Flexibility: changing the pool in the rubric flows through to the card.
    import json
    rubric_path = profile / "data" / "grading" / "talent-rubric.json"
    rubric = json.loads(rubric_path.read_text())
    rubric["pool"] = "ex-FAANG-designers"
    rubric_path.write_text(json.dumps(rubric))
    proc2 = subprocess.run([sys.executable, "-m", "ernest.cli", "grade", "--talent"],
                           cwd=str(ROOT), env=env, text=True, capture_output=True, check=False)
    check("re-grade exits 0", proc2.returncode == 0)
    talent2 = next(watch_dir.glob("talent-grades--*.md"), None)
    check("pool name is configurable (not hardcoded)",
          talent2 is not None and "ex-FAANG-designers" in talent2.read_text())


def test_self_repair_doctor() -> None:
    profile = Path(tempfile.mkdtemp(prefix="ernest_doc_"))
    vault = Path(tempfile.mkdtemp(prefix="ernest_doc_vault_"))
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
    proc = subprocess.run([sys.executable, "-m", "ernest.cli", "doctor"],
                          cwd=str(ROOT), env=env, text=True, capture_output=True, check=False)
    check("doctor still exits 0 with full package", proc.returncode == 0)
    check("doctor emits diagnostics block", "diagnostics:" in proc.stdout)
    check("doctor points to self-repair", "/ernest-doctor" in proc.stdout)


def main() -> int:
    test_b2b()
    test_talent()
    test_scoring_breadth_and_sorting()
    test_cards()
    test_self_repair_doctor()
    if FAILURES:
        print("FAILED grading tests:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("PASS - ICP grading (B2B + talent)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
