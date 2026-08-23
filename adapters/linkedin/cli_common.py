"""Shared CLI contract for the LinkedIn adapters.

One contract, so `ingest.py` and `act.py` behave identically and a scheduled
agent can drive either without special-casing:

  exit codes      0 ok · 2 usage · 3 not found · 4 unreachable/auth
                  5 upstream · 6 refused (cap/policy) · 7 rate limited · 10 config
  --agent         implies --json --compact, never prompts, never colors
  --deliver       stdout | file:<path> (atomic) | webhook:<url>
  --profile       a saved set of flag values, for cron jobs that always run the
                  same way; explicit flags always win
  --dry-run       show what would happen, change nothing
  feedback        one line about what surprised you, stored locally

Every command answers in a provenance envelope. A caller must always be able to
tell live data from cached data from a partial mirror, without guessing:

  {"meta": {"source": ..., "rung": N, "synced_at": ..., "reason": ...},
   "results": {...}}

Stdlib only, like the rest of the engine.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

OK, USAGE, NOT_FOUND, UNREACHABLE, UPSTREAM, REFUSED, RATE_LIMITED, CONFIG = 0, 2, 3, 4, 5, 6, 7, 10

EXIT_MEANING = {
    OK: "success",
    USAGE: "usage error (wrong arguments)",
    NOT_FOUND: "nothing to work on",
    UNREACHABLE: "no rung could reach LinkedIn (signed out, or no browser)",
    UPSTREAM: "LinkedIn returned something unusable",
    REFUSED: "refused by policy — a cap, an unapproved batch, or a never_auto action",
    RATE_LIMITED: "backing off; retry later",
    CONFIG: "config error (missing profile, bad ernest.yaml)",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def envelope(results: Any, *, source: str, rung: Optional[int] = None,
             reason: str = "", **extra: Any) -> Dict[str, Any]:
    meta: Dict[str, Any] = {"source": source, "synced_at": now_iso()}
    if rung is not None:
        meta["rung"] = rung
    if reason:
        meta["reason"] = reason
    meta.update(extra)
    return {"meta": meta, "results": results}


# --------------------------------------------------------------------------- #
# Delivery
# --------------------------------------------------------------------------- #

def deliver(body: str, sink: str) -> int:
    """stdout | file:<path> | webhook:<url>. Unknown schemes are refused, not guessed."""
    if sink in ("", "stdout"):
        print(body)
        return OK
    if sink.startswith("file:"):
        path = Path(sink[5:]).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(body + "\n", encoding="utf-8")
        os.replace(tmp, path)  # atomic: a half-written report is worse than none
        return OK
    if sink.startswith("webhook:"):
        url = sink[len("webhook:"):]
        req = urllib.request.Request(url, data=body.encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                if resp.status >= 300:
                    print(f"deliver: {url} returned HTTP {resp.status}", file=sys.stderr)
                    return UPSTREAM
        except (urllib.error.URLError, OSError) as exc:
            print(f"deliver: {url} failed ({exc})", file=sys.stderr)
            return UPSTREAM
        return OK
    print(f"deliver: unknown sink {sink!r}. Supported: stdout, file:<path>, webhook:<url>",
          file=sys.stderr)
    return USAGE


def emit(payload: Dict[str, Any], *, as_json: bool, compact: bool, sink: str,
         human: str = "") -> int:
    if as_json:
        body = json.dumps(payload, separators=(",", ":")) if compact else json.dumps(payload, indent=2)
    else:
        body = human or json.dumps(payload, indent=2)
    return deliver(body, sink)


# --------------------------------------------------------------------------- #
# Named profiles — for the cron job that always runs the same way
# --------------------------------------------------------------------------- #

def _profiles_path(profile_dir: Path) -> Path:
    return profile_dir / "data" / "linkedin" / "profiles.json"


def load_profiles(profile_dir: Path) -> Dict[str, Dict[str, Any]]:
    try:
        return json.loads(_profiles_path(profile_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_profile(profile_dir: Path, name: str, values: Dict[str, Any]) -> None:
    path = _profiles_path(profile_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_profiles(profile_dir)
    data[name] = {k: v for k, v in values.items() if v not in (None, False, "")}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def apply_profile(args: Any, profile_dir: Path, defaults: Dict[str, Any]) -> Optional[str]:
    """Precedence: explicit flag > profile value > default. Returns an error string."""
    name = getattr(args, "profile", None)
    if not name:
        return None
    stored = load_profiles(profile_dir).get(name)
    if stored is None:
        known = ", ".join(sorted(load_profiles(profile_dir))) or "none saved"
        return f"unknown profile {name!r} (known: {known})"
    for key, value in stored.items():
        if getattr(args, key, None) == defaults.get(key):   # untouched by the caller
            setattr(args, key, value)
    return None


# --------------------------------------------------------------------------- #
# Feedback — what surprised you, not a bug report
# --------------------------------------------------------------------------- #

def record_feedback(profile_dir: Path, note: str) -> Path:
    """Local-only, append-only. Never POSTed anywhere.

    Also mirrored into ernest's own feedback log so the improve loop sees it and
    can turn three independent signals of the same shape into a rubric proposal.
    """
    path = profile_dir / "logs" / "linkedin-feedback.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": now_iso(), "note": note}) + "\n")
    shared = profile_dir / "logs" / "feedback.jsonl"
    try:
        with shared.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": now_iso(), "note": note, "source": "linkedin"}) + "\n")
    except OSError:
        pass
    return path


def add_common_flags(ap: Any) -> None:
    ap.add_argument("--json", action="store_true", help="machine-readable envelope")
    ap.add_argument("--compact", action="store_true", help="single-line JSON")
    ap.add_argument("--agent", action="store_true",
                    help="implies --json --compact and never prompts")
    ap.add_argument("--deliver", default="stdout",
                    help="stdout | file:<path> | webhook:<url>")
    ap.add_argument("--profile", help="use a saved set of flag values")
    ap.add_argument("--dry-run", action="store_true", help="change nothing")


def resolve_common(args: Any) -> None:
    if getattr(args, "agent", False):
        args.json = True
        args.compact = True
