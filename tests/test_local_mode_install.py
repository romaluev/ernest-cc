#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    profile = Path(tempfile.mkdtemp(prefix="ernest_profile_"))
    vault = Path(tempfile.mkdtemp(prefix="ernest_vault_"))
    env = os.environ.copy()
    env.update({
        "ERNEST_PROFILE_DIR": str(profile),
        "ERNEST_LOCAL_VAULT": str(vault),
        "ERNEST_LOCAL_MEMORY_FILE": str(vault / "memory.json"),
    })
    proc = subprocess.run(
        ["bash", "install.sh"],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    failures: list[str] = []
    if proc.returncode != 0:
        failures.append(f"installer failed: {proc.stdout} {proc.stderr}")
    if "Here is what needs you right now" not in proc.stdout:
        failures.append("installer did not auto-show the first brief")
    if "start" not in proc.stdout:
        failures.append("installer did not surface the one-command 'start'")
    mcp_path = profile / ".mcp.json"
    if not mcp_path.exists():
        failures.append("generated .mcp.json missing")
    else:
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
        servers = data.get("mcpServers", {})
        if "ernest-brain" in servers:
            failures.append("local mode still includes ernest-brain")
        local_memory = servers.get("local-memory")
        if not local_memory:
            failures.append("local mode missing local-memory")
        elif local_memory.get("disabled") is True:
            failures.append("local-memory is disabled in local mode")
    if not (vault / "memory.json").exists():
        failures.append("local memory file missing")
    if not (profile / "data" / "README.md").exists():
        failures.append("local data fallback not installed")
    if not (profile / "data" / "mail" / "sample-thread.md").exists():
        failures.append("local mail sample not installed")
    if not (profile / "ernest" / "cli.py").exists():
        failures.append("engine not installed into profile")

    launcher = profile / "bin" / "ernest"
    if not launcher.exists():
        failures.append("ernest launcher not installed")
    else:
        run_env = os.environ.copy()
        run_env.update({
            "ERNEST_PROFILE_DIR": str(profile),
            "ERNEST_LOCAL_VAULT": str(vault),
            "ERNEST_TODAY": "2026-06-25",
        })
        for sub in ("doctor", "watch", "brief", "start"):
            res = subprocess.run(["bash", str(launcher), sub], text=True,
                                 capture_output=True, env=run_env, check=False)
            if res.returncode != 0:
                failures.append(f"installed launcher '{sub}' failed: {res.stderr}")
        brief_dir = vault / "Ernest" / "00-Daily"
        if not (brief_dir.exists() and list(brief_dir.glob("*.md"))):
            failures.append("installed launcher did not produce a brief")

    if failures:
        print("FAILED local-mode install:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("PASS - local mode install is independent of VPS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
