#!/usr/bin/env python3
"""Skills are well-formed and registered.

Each skill dir has a SKILL.md with `name` + `description` frontmatter, and every
connector use-case skill is listed in the library index and the connectors doc.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
INDEX = SKILLS / "ernest-library-index" / "SKILL.md"
CONNECTORS = ROOT / "docs" / "connectors.md"
FAILURES: list[str] = []

NEW_SKILLS = [
    "call-prep", "call-coaching", "support-triage",
    "hiring-pipeline", "lead-enrichment", "deal-desk",
]


def check(label: str, condition: bool) -> None:
    print(f"  [{'ok  ' if condition else 'FAIL'}] {label}")
    if not condition:
        FAILURES.append(label)


def frontmatter(text: str) -> dict[str, str]:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


def main() -> int:
    # Every skill dir is well-formed.
    for skill_md in sorted(SKILLS.glob("*/SKILL.md")):
        fm = frontmatter(skill_md.read_text(encoding="utf-8"))
        name = skill_md.parent.name
        check(f"{name}: has name+description", bool(fm.get("name") and fm.get("description")))

    index_text = INDEX.read_text(encoding="utf-8") if INDEX.is_file() else ""
    connectors_text = CONNECTORS.read_text(encoding="utf-8") if CONNECTORS.is_file() else ""

    for name in NEW_SKILLS:
        check(f"{name}: SKILL.md exists", (SKILLS / name / "SKILL.md").is_file())
        check(f"{name}: in library index", name in index_text)

    # The stack map names the real tools so connectors stay discoverable.
    for tool in ["HubSpot", "Fireflies", "Clay", "Apollo", "Ironclad",
                 "Pylon", "Zendesk", "Intercom", "Notion", "Ashby", "Hex"]:
        check(f"connectors.md maps {tool}", tool in connectors_text)

    # call-prep ships its one-pager reference + a command.
    check("call-prep one-pager reference", (SKILLS / "call-prep" / "references" / "one-pager.md").is_file())
    check("/ernest-call-prep command", (ROOT / "commands" / "ernest-call-prep.md").is_file())

    if FAILURES:
        print("FAILED skills tests:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("PASS - skills well-formed and registered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
