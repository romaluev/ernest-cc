#!/usr/bin/env python3
"""Skill contract: the anti-drift net for the deepened skill layer.

Five guarantees:
  1. skills-pack/ mirrors its 7 skills byte-for-byte (drift prints the remedy).
  2. The weights documented in the grading skills match ernest/grading.py
     constants (docs stay subordinate to code).
  3. Deepened skills carry their required sections; card-writing skills carry
     the standard reply line.
  4. The new-automation template formats cleanly and teaches the same house
     shape as ernest-use-case-author.
  5. No real names leak into skills/** (fictional sample world only).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILURES = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global FAILURES
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES += 1


PACK_SKILLS = ["account-followup-recovery", "add-collaborator", "candidate-followup",
               "list-sync", "slack-task-tracker", "sourcing-pipeline",
               "talent-sourcing-grading"]

V2_HEADERS = ["## When to use", "## Parameters", "## Data sources", "## Watch half",
              "## Decision criteria", "## Draft half", "## Output",
              "## Failure modes", "## Verification"]

# Wave-grown: every deepened skill declares its required `## `-header substrings.
CONTRACT: dict[str, list[str]] = {
    "sourcing-pipeline": V2_HEADERS,
    "candidate-followup": V2_HEADERS,
    "add-collaborator": V2_HEADERS,
    "list-sync": V2_HEADERS,
    "slack-task-tracker": V2_HEADERS,
    "inbox-prospect-followup": ["## Decision criteria", "## Draft", "## Output",
                                "## Failure modes", "## Verification"],
    "linkedin-invitations": V2_HEADERS + ["## Prerequisites", "## When NOT to use",
                                          "## Fallbacks", "## Exit codes", "## Edge cases"],
    "support-triage": ["## Decision criteria", "## Draft", "## Output",
                       "## Failure modes", "## Verification"],
    "b2b-lead-grading": ["## Signal priority", "## Decision criteria", "## Output",
                         "## Verification", "## Hard rules"],
    "talent-sourcing-grading": ["### Decision criteria", "## Output", "## Verification",
                                "## Hard rules"],
    "ernest-watch": ["## Canonical Reminder Card", "## Data Source Order", "## Run Sequence"],
    "ernest-use-case-author": ["## New Skill Template", "## Proposal Format"],
    "ernest-self-repair": ["## 1. Diagnose", "## 2. Heal first", "## 5. Verify"],
}

FOOTER = "Reply draft these when you want me to prepare actions."
CARD_SKILLS = ["sourcing-pipeline", "candidate-followup", "add-collaborator",
               "list-sync", "slack-task-tracker", "inbox-prospect-followup",
               "linkedin-invitations", "ernest-watch"]

# Row-label -> weight-key mapping for the docs-vs-code parity check.
B2B_ROWS = {"categories": "category", "providers": "provider", "companies": "company",
            "people": "person", "intent_keywords": "intent",
            "CEO reference": "reputation_or_prior", "Fund": "large_fund"}
TALENT_ROWS = {"big_tech`)": "senior_at_big_tech", "strong_tech_keywords": "strong_tech",
               "ai_media_models": "ai_media", "Tier-1 country | +": "commercial_in_tier1_country"}


def _skill_text(name: str) -> str:
    return (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


def main() -> int:
    # 1. Pack parity, both directions.
    for name in PACK_SKILLS:
        src_dir, pack_dir = ROOT / "skills" / name, ROOT / "skills-pack" / name
        check(f"pack dir exists: {name}", pack_dir.is_dir())
        if not pack_dir.is_dir():
            continue
        src_files = {p.relative_to(src_dir) for p in src_dir.rglob("*") if p.is_file()}
        pack_files = {p.relative_to(pack_dir) for p in pack_dir.rglob("*") if p.is_file()}
        same_set = src_files == pack_files
        same_bytes = same_set and all(
            (src_dir / rel).read_bytes() == (pack_dir / rel).read_bytes() for rel in src_files)
        check(f"pack parity: {name}", same_set and same_bytes,
              f"fix: cp -R skills/{name}/ skills-pack/{name}/")

    # 2. Weights parity: grading docs vs code.
    from ernest import grading
    b2b_text = _skill_text("b2b-lead-grading")
    for row, key in B2B_ROWS.items():
        line = next((l for l in b2b_text.splitlines() if row in l), "")
        want = f"+{int(grading.B2B_WEIGHTS[key])}"
        check(f"b2b weight documented: {key} {want}", want in line, f"row '{row}' -> '{line[:80]}'")
    check("b2b CRM base 100 documented", "score 100" in b2b_text)
    check("b2b CRM tier-2 base 60 documented", "60" in b2b_text)
    check("b2b default tier-2 score documented",
          f"score {int(grading.DEFAULT_TIER2_SCORE)}" in b2b_text)
    tal_text = _skill_text("talent-sourcing-grading")
    for row, key in TALENT_ROWS.items():
        line = next((l for l in tal_text.splitlines() if row in l), "")
        want = f"+{int(grading.TALENT_WEIGHTS[key])}"
        check(f"talent weight documented: {key} {want}", want in line, f"row '{row}' -> '{line[:80]}'")
    for key in ("t2_big_tech", "t2_us_startup", "t2_gtm", "t2_country"):
        want = f"+{int(grading.TALENT_WEIGHTS[key])}"
        check(f"talent tier-2 weight documented: {key} {want}", want in tal_text)

    # 3. Section contract + footer + engine-optional framing for pack skills.
    for name, headers in CONTRACT.items():
        text = _skill_text(name)
        missing = [h for h in headers if h not in text]
        check(f"sections present: {name}", not missing, f"missing {missing}")
    for name in CARD_SKILLS:
        check(f"standard reply line: {name}", FOOTER in _skill_text(name))
    for name in PACK_SKILLS:
        text = _skill_text(name)
        if "## Verification" in text:
            check(f"engine-optional verification: {name}",
                  "engine optional" in text.lower() or "engine baseline" in text.lower()
                  or "if the ernest engine" in text.lower())

    # 4. Template sanity (both homes teach the same shape).
    from ernest.automations import _SKILL_TEMPLATE
    try:
        out = _SKILL_TEMPLATE.format(id="x", description="d", title="X",
                                     playbook="account-followup-recovery",
                                     params="- staleness: 7d")
    except (KeyError, ValueError, IndexError) as exc:
        out = f"FORMAT ERROR: {exc}"
    check("scaffold template formats cleanly", out.startswith("---\nname:"), out[:60])
    for h in V2_HEADERS:
        check(f"scaffold template has {h}", h in out)
    author = _skill_text("ernest-use-case-author")
    for h in V2_HEADERS:
        check(f"author template teaches {h}", h in author)

    # 5. Fictional-world guard (mirrors tests/test_docs.py's pair).
    leaks = []
    for path in (ROOT / "skills").rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        if "Manoj" in text or "Brightpay" in text:
            leaks.append(str(path.relative_to(ROOT)))
    check("no real names in skills/**", not leaks, ", ".join(leaks))

    if FAILURES:
        print(f"FAIL - skill contract ({FAILURES} failure(s))")
        return 1
    print("PASS - skill contract: pack parity, weights honesty, sections, template, names")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
