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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    try:
        soul = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    except OSError:
        print("{}")
        return 0
    context = (
        "You are Ernest, operating as an installed plugin. The following is your "
        "always-on identity and hard rules — honor them for the entire session:\n\n"
        + soul
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
