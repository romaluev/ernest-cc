#!/usr/bin/env python3
"""Brain connect / go-local: durable mode, secret-safe MCP entry, reversibility,
and the hardening from the pre-push review (graceful CLI failure, no template
corruption, input robustness)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FAILURES: list[str] = []

SECRET = "tok-must-never-touch-disk-1234567890"


def check(label: str, condition: bool) -> None:
    print(f"  [{'ok  ' if condition else 'FAIL'}] {label}")
    if not condition:
        FAILURES.append(label)


def fresh_profile() -> Path:
    p = Path(tempfile.mkdtemp(prefix="ernest_connect_"))
    os.environ["ERNEST_PROFILE_DIR"] = str(p)
    return p


def main() -> int:
    os.environ["ERNEST_NO_CLI"] = "1"        # never shell out to a real `claude`
    os.environ["ERNEST_BRAIN_TOKEN"] = SECRET
    os.environ.pop("ERNEST_MODE", None)
    os.environ.pop("ERNEST_BRAIN_URL", None)

    from ernest import config, connect

    # --- happy path -----------------------------------------------------------
    profile = fresh_profile()
    cfg = config.load()
    check("starts local (no connection.json)", cfg.mode == "local")

    check("connect returns 0", connect.connect(cfg, "https://brain.example.com/") == 0)
    conn = json.loads(cfg.connection_file.read_text())
    check("connection.json mode=vps", conn.get("mode") == "vps")
    check("connection.json url normalized (no trailing slash)",
          conn.get("brain_url") == "https://brain.example.com")

    server = json.loads(cfg.mcp_file.read_text()).get("mcpServers", {}).get("ernest-brain", {})
    check("mcp entry http + url", server.get("type") == "http" and server.get("url") == "https://brain.example.com")
    check("auth header is a placeholder, not the secret",
          server.get("headers", {}).get("Authorization") == "Bearer ${ERNEST_BRAIN_TOKEN}")

    leaked = any(p.is_file() and SECRET in p.read_text(encoding="utf-8", errors="ignore")
                 for p in profile.rglob("*"))
    check("bearer secret never written to disk", not leaked)
    check("mode persists across load() via connection.json", config.load().mode == "vps")

    # --- resolve_url precedence ----------------------------------------------
    cfg2 = config.load()
    check("resolve_url falls back to persisted", connect.resolve_url(cfg2) == "https://brain.example.com")
    os.environ["ERNEST_BRAIN_URL"] = "https://env-wins.example.com"
    check("resolve_url: env beats persisted", connect.resolve_url(cfg2) == "https://env-wins.example.com")
    check("resolve_url: explicit beats env",
          connect.resolve_url(cfg2, "https://explicit.example.com") == "https://explicit.example.com")
    os.environ.pop("ERNEST_BRAIN_URL", None)

    # --- go-local fully reverses ---------------------------------------------
    check("go_local returns 0", connect.go_local(cfg2) == 0)
    check("go_local sets mode=local", json.loads(cfg.connection_file.read_text()).get("mode") == "local")
    check("go_local removes ernest-brain", "ernest-brain" not in
          json.loads(cfg.mcp_file.read_text()).get("mcpServers", {}))
    check("fresh load() is local again", config.load().mode == "local")

    # --- input robustness -----------------------------------------------------
    check("rejects non-http url", connect.connect(cfg, "ftp://nope") == 2)
    p2 = fresh_profile(); cfg3 = config.load()
    check("accepts uppercase scheme (RFC: schemes are case-insensitive)",
          connect.connect(cfg3, "HTTPS://Brain.Example.com") == 0)

    # non-string / garbage persisted mode degrades to local
    p3 = fresh_profile(); cfg4 = config.load()
    cfg4.connection_file.write_text(json.dumps({"mode": 123}))
    check("non-string mode degrades to local", config.load().mode == "local")
    cfg4.connection_file.write_text(json.dumps({"mode": "garbage"}))
    check("unknown mode string degrades to local", config.load().mode == "local")

    # --- preserves unrelated servers + top-level keys ------------------------
    p4 = fresh_profile(); cfg5 = config.load()
    cfg5.mcp_file.write_text(json.dumps({
        "mcpServers": {"local-memory": {"type": "stdio", "command": "x"}},
        "_meta": "keep me",
    }))
    connect.connect(cfg5, "https://b.example.com")
    after = json.loads(cfg5.mcp_file.read_text())
    check("connect preserves other servers", "local-memory" in after.get("mcpServers", {}))
    check("connect preserves top-level keys", after.get("_meta") == "keep me")
    connect.go_local(cfg5)
    after2 = json.loads(cfg5.mcp_file.read_text())
    check("go_local keeps other servers + keys", "local-memory" in after2.get("mcpServers", {})
          and after2.get("_meta") == "keep me")

    # --- malformed .mcp.json on connect doesn't crash ------------------------
    p5 = fresh_profile(); cfg6 = config.load()
    cfg6.mcp_file.write_text("{ this is not json")
    check("connect survives malformed .mcp.json", connect.connect(cfg6, "https://c.example.com") == 0)
    check("connect rewrites valid json with brain", "ernest-brain" in
          json.loads(cfg6.mcp_file.read_text()).get("mcpServers", {}))

    # --- never mutate a git-tracked .mcp.json template -----------------------
    p6 = fresh_profile(); cfg7 = config.load()
    try:
        subprocess.run(["git", "init", "-q"], cwd=str(p6), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(p6), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=str(p6), check=True, capture_output=True)
        template = '{\n  "mcpServers": {\n    "ernest-brain": {\n      "url": "${ERNEST_BRAIN_URL}"\n    }\n  }\n}\n'
        cfg7.mcp_file.write_text(template)
        subprocess.run(["git", "add", ".mcp.json"], cwd=str(p6), check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "tmpl"], cwd=str(p6), check=True, capture_output=True)
        connect.connect(cfg7, "https://real.example.com")
        check("git-tracked .mcp.json template is left untouched",
              cfg7.mcp_file.read_text() == template)
    except (OSError, subprocess.CalledProcessError):
        check("git available for tracked-template test (skipped)", True)

    # --- _claude_cli is exception-safe (TOCTOU/perms) ------------------------
    os.environ.pop("ERNEST_NO_CLI", None)
    real_which, real_run = connect.shutil.which, connect.subprocess.run
    connect.shutil.which = lambda _x: "/usr/bin/claude"
    def boom(*_a, **_k):
        raise OSError("exec format error")
    connect.subprocess.run = boom
    try:
        check("_claude_cli returns None on exec failure (no raise)", connect._claude_cli("mcp", "list") is None)
        # And the public flow stays graceful with a broken CLI mid-connect.
        p7 = fresh_profile(); cfg8 = config.load()
        check("connect returns 0 even if claude exec fails", connect.connect(cfg8, "https://d.example.com") == 0)
        check("connect still persisted vps mode despite CLI failure", config.load().mode == "vps")
    finally:
        connect.shutil.which, connect.subprocess.run = real_which, real_run
        os.environ["ERNEST_NO_CLI"] = "1"

    if FAILURES:
        print("FAILED connect tests:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("PASS - brain connect / go-local")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
