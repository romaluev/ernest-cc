#!/usr/bin/env python3
"""Verify scripts/demo.sh runs clean end-to-end and produces real artifacts."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    proc = subprocess.run(
        ["bash", str(ROOT / "scripts" / "demo.sh")],
        text=True, capture_output=True, check=False,
    )
    failures: list[str] = []
    if proc.returncode != 0:
        failures.append(f"demo exited {proc.returncode}: {proc.stderr}")

    out = proc.stdout
    for needle in ("Morning brief", "00-Watch", "00-Daily", "00-Drafts",
                   "Adopted proposal", "partner-renewals"):
        if needle not in out:
            failures.append(f"demo output missing '{needle}'")

    match = re.search(r"^Vault:\s+(.+)$", out, re.M)
    if match:
        vault = Path(match.group(1).strip())
        if not list((vault / "Ernest" / "00-Drafts").glob("*.md")):
            failures.append("demo produced no draft artifact")

    if failures:
        print("FAILED demo:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("PASS - demo runs end-to-end and produces artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
