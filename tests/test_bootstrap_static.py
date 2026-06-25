#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    proc = subprocess.run(
        ["bash", "install.sh", "--health-only"],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        print("FAILED bootstrap health-only")
        print(proc.stdout)
        print(proc.stderr)
        return 1
    if "Ernest health check: ok" not in proc.stdout:
        print("FAILED missing success marker")
        print(proc.stdout)
        return 1
    print("PASS - bootstrap health-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
