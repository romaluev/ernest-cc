#!/usr/bin/env python3
"""SessionStart hook: load Ernest's identity + hard rules in plugin mode.

A Claude Code/Cowork plugin does NOT auto-load a bundled CLAUDE.md, so without
this the persona and the draft-first hard rules would silently not apply when
Ernest is installed as a plugin. We inject CLAUDE.md as additionalContext at the
start of every session. (In project mode CLAUDE.md auto-loads and this hook is
not used, so there's no double-load.)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    try:
        soul = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    except OSError:
        print("{}")
        return 0
    # In plugin mode (Cowork / a global plugin) there is no `ernest` binary on PATH,
    # so tell the model exactly how to reach the deterministic engine that ships
    # inside the plugin, and where to read/write state.
    vault = os.environ.get("ERNEST_LOCAL_VAULT") or os.path.expanduser("~/ErnestVault")
    profile = os.environ.get("ERNEST_PROFILE_DIR") or str(ROOT)
    engine = (
        "\n\n## Running the engine (plugin mode)\n"
        "There may be no `ernest` command on PATH. The deterministic engine ships in "
        f"this plugin. Run it as:\n\n"
        f"    PYTHONPATH=\"{ROOT}\" ERNEST_PROFILE_DIR=\"{profile}\" "
        f"ERNEST_LOCAL_VAULT=\"{vault}\" python3 -m ernest.cli <command>\n\n"
        "Commands: start · watch · brief · grade [--talent] · read --owed · "
        "draft --concern <id> · render · doctor · onboard · schedule. It needs no "
        "model/network and writes cards to the vault above. Prefer a bare `ernest "
        "<command>` only if that binary exists (terminal install)."
    )
    context = (
        "You are Ernest, operating as an installed plugin. The following is your "
        "always-on identity and hard rules — honor them for the entire session:\n\n"
        + soul + engine
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
