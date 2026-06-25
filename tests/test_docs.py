#!/usr/bin/env python3
"""Docs are present and cover the CEO prompt catalog."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "docs" / "examples.md"

REQUIRED_DOCS = [
    "docs/README.md",
    "docs/quickstart.md",
    "docs/examples.md",
    "docs/daily-use.md",
    "docs/add-automation.md",
]

REQUIRED_PROMPTS = [
    "ernest start",
    "Manoj",
    "Alua",
    "Nubank",
    "korea-list-sync",
    "press-list-sync",
    "partnership-sourcing",
    "slack-task-tracking",
    "draft these",
    "/ernest-new-automation",
]


def main() -> int:
    failures: list[str] = []
    for rel in REQUIRED_DOCS:
        if not (ROOT / rel).is_file():
            failures.append(f"missing doc: {rel}")
    if EXAMPLES.is_file():
        text = EXAMPLES.read_text(encoding="utf-8")
        for needle in REQUIRED_PROMPTS:
            if needle not in text:
                failures.append(f"examples.md missing: {needle}")
    if failures:
        print("FAILED docs:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS - docs and prompt catalog complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
