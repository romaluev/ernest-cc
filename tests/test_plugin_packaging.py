#!/usr/bin/env python3
"""Blocker 1+2 — ernest-cc must be a VALID Claude Code/Cowork plugin.

Verifies the manifest is metadata-only (no invented `entrypoints`), the hooks are
declared in hooks/hooks.json with ${CLAUDE_PLUGIN_ROOT}, a marketplace.json exists
for no-terminal install, and the SessionStart handler injects the persona + hard
rules (since plugins don't auto-load CLAUDE.md).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILURES: list[str] = []


def check(label: str, cond: bool) -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label}")
    if not cond:
        FAILURES.append(label)


def _json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def test_plugin_manifest() -> None:
    pj = _json(ROOT / ".claude-plugin" / "plugin.json")
    check("plugin.json valid + has name", pj.get("name") == "ernest-cc")
    check("plugin.json drops invented 'entrypoints'", "entrypoints" not in pj)
    check("plugin.json has version", bool(pj.get("version")))


def test_hooks_manifest() -> None:
    hj = _json(ROOT / "hooks" / "hooks.json")
    hooks = hj.get("hooks", {})
    check("hooks.json declares PreToolUse/Stop/SessionStart",
          all(k in hooks for k in ("PreToolUse", "Stop", "SessionStart")))
    blob = json.dumps(hj)
    check("hooks use ${CLAUDE_PLUGIN_ROOT} (not $CLAUDE_PROJECT_DIR/relative)",
          "${CLAUDE_PLUGIN_ROOT}" in blob and "$CLAUDE_PROJECT_DIR" not in blob)
    check("PreToolUse matches all tools", hooks["PreToolUse"][0].get("matcher") == "*")


def test_marketplace() -> None:
    mp = _json(ROOT / ".claude-plugin" / "marketplace.json")
    names = [p.get("name") for p in mp.get("plugins", [])]
    check("marketplace.json lists ernest-cc", "ernest-cc" in names)
    check("marketplace.json has owner", bool(mp.get("owner")))


def test_session_start_injects_persona() -> None:
    proc = subprocess.run([sys.executable, str(ROOT / "hooks" / "session_context.py")],
                          text=True, capture_output=True, check=False)
    check("session_context exits 0", proc.returncode == 0)
    out = json.loads(proc.stdout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    check("SessionStart event name correct", out["hookSpecificOutput"]["hookEventName"] == "SessionStart")
    check("persona/identity injected", "Ernest" in ctx)
    check("hard rule injected (draft-first)", "draft-first" in ctx.lower() or "draft" in ctx.lower())


def test_project_settings_present() -> None:
    st = _json(ROOT / ".claude" / "settings.json")
    check(".claude/settings.json wires PreToolUse", "PreToolUse" in st.get("hooks", {}))
    check("project settings use $CLAUDE_PROJECT_DIR", "$CLAUDE_PROJECT_DIR" in json.dumps(st))


if __name__ == "__main__":
    test_plugin_manifest()
    test_hooks_manifest()
    test_marketplace()
    test_session_start_injects_persona()
    test_project_settings_present()
    if FAILURES:
        print(f"FAILED {len(FAILURES)}:")
        for f in FAILURES:
            print("  -", f)
        raise SystemExit(1)
    print("PASS - ernest-cc is a valid plugin (manifest, hooks, marketplace, persona injection)")
