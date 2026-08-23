#!/usr/bin/env python3
"""Find an earlier Ernest install and adopt everything worth keeping.

Someone who "already tried this once" has a profile somewhere with real value in
it: their memory, their tuned rubrics, their exported data, their custom skills,
and — easy to overlook — their LEARNING HISTORY. Overrides, applied proposals,
and feedback are what make grading get better; losing them silently resets the
system to day one while looking like a clean install.

install.sh preserves a profile IN PLACE. This handles the other case: a prior
install at a DIFFERENT path (an old clone, a plugin copy, a renamed home dir).

Rules:
  - Back up before touching anything in the target.
  - Never overwrite a newer target file with an older source file.
  - Never merge secrets blindly: `env` and `.mcp.json` are copied 0600, and only
    when the target has none.
  - Additive only. Nothing is deleted from either side.
  - Idempotent: a second run finds nothing left to do.

    python3 scripts/migrate.py --discover              # what is out there
    python3 scripts/migrate.py --dry-run               # what it would adopt
    python3 scripts/migrate.py --from <dir>            # adopt a specific one
    python3 scripts/migrate.py                         # adopt the best candidate
"""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# What makes a directory an Ernest profile rather than a lookalike.
MARKERS = ("memory/company-core.md", "ernest.yaml")

# What is worth carrying over, and how to merge it.
#   tree   copy missing files; newer-wins for files present on both sides
#   jsonl  append-only union, deduped, chronologically stable
#   secret copy only when the target has none, mode 0600
ADOPT = [
    ("memory", "tree", "who you are, your ICP, your standing concerns"),
    ("data", "tree", "exports and tuned grading rubrics"),
    ("custom", "tree", "your own skills, commands, and agents"),
    ("logs/feedback.jsonl", "jsonl", "taste corrections"),
    ("logs/linkedin-feedback.jsonl", "jsonl", "LinkedIn corrections"),
    ("logs/linkedin-decisions.jsonl", "jsonl", "decision journal — the learning signal"),
    ("logs/learning-proposals.jsonl", "jsonl", "pending improvement proposals"),
    ("logs/applied.jsonl", "jsonl", "applied changes (needed for rollback)"),
    ("logs/usage.jsonl", "jsonl", "usage telemetry"),
    ("connection.json", "file", "local vs VPS wiring"),
    ("env", "secret", "connector environment"),
    (".mcp.json", "secret", "MCP connector wiring"),
]

SEARCH_ROOTS = ["~/.ernest-cc", "~/ernest-cc", "~/Projects/ernest-cc",
                "~/Documents/ernest-cc", "~/Desktop/ernest-cc", "~/.ernest",
                "~/Library/Application Support/ernest-cc"]


def is_source_checkout(path: Path) -> bool:
    """A git clone of the repo is not a profile — it ships the sample world and
    gets replaced wholesale by every refresh. Adopting from one would import
    placeholder identity over real memory."""
    return (path / "install.sh").exists() and (
        (path / ".git").exists() or (path / "tests").is_dir())


def is_profile(path: Path) -> bool:
    if not path.is_dir() or not all((path / m).exists() for m in MARKERS):
        return False
    return not is_source_checkout(path)


def _launchd_paths() -> List[Path]:
    """Old scheduled jobs point at wherever the last install lived."""
    out: List[Path] = []
    la = Path.home() / "Library" / "LaunchAgents"
    if not la.is_dir():
        return out
    for plist in la.glob("*ernest*.plist"):
        try:
            data = plistlib.loads(plist.read_bytes())
        except Exception:  # noqa: BLE001 — a malformed plist is not our problem
            continue
        for arg in data.get("ProgramArguments", []):
            if isinstance(arg, str) and "ernest" in arg:
                for token in arg.replace('"', " ").split():
                    p = Path(token)
                    if p.name == "ernest" and p.parent.name == "bin":
                        out.append(p.parent.parent)
    return out


def discover(target: Path) -> List[Dict[str, Any]]:
    seen: set = set()
    found: List[Dict[str, Any]] = []
    candidates = [Path(r).expanduser() for r in SEARCH_ROOTS]
    candidates += list((Path.home() / ".claude" / "plugins").glob("**/ernest-cc"))
    candidates += _launchd_paths()
    env = os.environ.get("ERNEST_PROFILE_DIR")
    if env:
        candidates.append(Path(env))
    for path in candidates:
        try:
            path = path.expanduser().resolve()
        except OSError:
            continue
        if path in seen or not is_profile(path):
            continue
        seen.add(path)
        core = (path / "memory" / "company-core.md")
        try:
            head = core.read_text(encoding="utf-8")[:400]
        except OSError:
            head = ""
        company = next((ln.split(":", 1)[1].strip()
                        for ln in head.splitlines() if ln.lower().startswith("- company:")),
                       "")
        if not company and head.startswith("# Company Core"):
            company = head.splitlines()[0].replace("# Company Core", "").strip(" —-") or "unknown"
        found.append({
            "path": str(path),
            "is_target": path == target,
            "company": company or "unknown",
            "onboarded": (path / "vault" / ".onboarded").exists(),
            "sample_world": "Northwind" in head,
            "mtime": max((p.stat().st_mtime for p in path.rglob("*") if p.is_file()), default=0),
            "has": [name for name, _, _ in ADOPT if (path / name).exists()],
        })
    found.sort(key=lambda c: (c["is_target"], -c["mtime"]))
    return found


def best_source(target: Path) -> Optional[Dict[str, Any]]:
    """The richest non-target profile. Real identity beats a sample world."""
    others = [c for c in discover(target) if not c["is_target"]]
    if not others:
        return None
    others.sort(key=lambda c: (c["sample_world"], -len(c["has"]), -c["mtime"]))
    return others[0]


def _backup(target: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = target / ".backups" / f"pre-migrate-{stamp}"
    dest.mkdir(parents=True, exist_ok=True)
    for name, kind, _ in ADOPT:
        src = target / name
        if not src.exists():
            continue
        out = dest / name
        out.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, out, dirs_exist_ok=True)
        else:
            shutil.copy2(src, out)
    return dest


def _merge_jsonl(src: Path, dst: Path, dry: bool) -> int:
    """Union, deduped on the raw line. Append-only history stays append-only."""
    if not src.is_file():
        return 0
    existing = set()
    if dst.is_file():
        existing = {ln for ln in dst.read_text(encoding="utf-8").splitlines() if ln.strip()}
    new = [ln for ln in src.read_text(encoding="utf-8").splitlines()
           if ln.strip() and ln not in existing]
    if new and not dry:
        dst.parent.mkdir(parents=True, exist_ok=True)
        with dst.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(new) + "\n")
    return len(new)


def _is_pristine(target_file: Path, rel: Path, pristine_root: Optional[Path]) -> bool:
    """True when the target file is byte-identical to what the repo ships.

    This is the crux of the whole migration. A fresh `install.sh` writes the
    SAMPLE world with a brand-new mtime, so a naive newer-wins rule lets
    placeholder identity beat the user's real `company-core.md` — the exact file
    they care most about. Shipped sample content is not user content, and it
    never outranks a real profile.
    """
    if pristine_root is None:
        return False
    shipped = pristine_root / rel
    if not shipped.is_file() or not target_file.is_file():
        return False
    try:
        return shipped.read_bytes() == target_file.read_bytes()
    except OSError:
        return False


def _merge_tree(src: Path, dst: Path, dry: bool,
                pristine_root: Optional[Path] = None) -> int:
    """Copy missing files. On a collision the newer wins — UNLESS the target is
    untouched shipped sample content, in which case the source always wins."""
    if not src.is_dir():
        return 0
    n = 0
    for path in src.rglob("*"):
        if not path.is_file() or "/.backups/" in str(path):
            continue
        rel = path.relative_to(src)
        out = dst / rel
        if out.exists():
            newer = out.stat().st_mtime >= path.stat().st_mtime
            if newer and not _is_pristine(out, Path(dst.name) / rel, pristine_root):
                continue
        n += 1
        if not dry:
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, out)
    return n


def migrate(target: Path, source: Path, dry: bool = False,
            pristine_root: Optional[Path] = None) -> Dict[str, Any]:
    if source.resolve() == target.resolve():
        return {"ok": False, "why": "source and target are the same profile"}
    if not is_profile(source):
        return {"ok": False, "why": f"{source} does not look like an Ernest profile"}
    # The repo we were run from IS the pristine reference for "shipped sample".
    if pristine_root is None:
        here = Path(__file__).resolve().parents[1]
        pristine_root = here if is_source_checkout(here) else None
    backup = None if dry else _backup(target)
    adopted: List[Dict[str, Any]] = []
    for name, kind, why in ADOPT:
        src, dst = source / name, target / name
        if not src.exists():
            continue
        if kind == "tree":
            n = _merge_tree(src, dst, dry, pristine_root)
        elif kind == "jsonl":
            n = _merge_jsonl(src, dst, dry)
        elif kind == "secret":
            # Never merge secrets. Copy only into an empty slot, owner-only.
            if dst.exists():
                adopted.append({"what": name, "count": 0, "why": why,
                                "note": "target already has one — left alone"})
                continue
            n = 1
            if not dry:
                shutil.copy2(src, dst)
                os.chmod(dst, 0o600)
        else:
            n = 0 if dst.exists() else 1
            if n and not dry:
                shutil.copy2(src, dst)
        if n:
            adopted.append({"what": name, "count": n, "why": why})
    # The "onboarded" marker lives in the VAULT, not the profile, so it does not
    # travel with memory/. Without it every report keeps warning about SAMPLE
    # data even though real identity was just adopted. Re-derive it from what the
    # memory actually says rather than copying a file across vaults.
    marker = _mark_onboarded(target, dry)
    if marker:
        adopted.append({"what": "onboarded marker", "count": 1,
                        "why": "adopted memory is real, not the sample world"})

    return {"ok": True, "source": str(source), "target": str(target),
            "backup": str(backup) if backup else None, "dry_run": dry,
            "adopted": adopted}


def _mark_onboarded(target: Path, dry: bool) -> bool:
    """Write the vault's onboarded marker when the profile's memory is real."""
    core = target / "memory" / "company-core.md"
    try:
        text = core.read_text(encoding="utf-8")
    except OSError:
        return False
    if "Northwind" in text or not text.strip():
        return False   # still the shipped sample world — do not claim otherwise
    vault = Path(os.environ.get("ERNEST_LOCAL_VAULT") or (target / "vault"))
    marker = vault / ".onboarded"
    if marker.exists():
        return False
    if not dry:
        vault.mkdir(parents=True, exist_ok=True)
        company = next((ln.split(":", 1)[1].strip() for ln in text.splitlines()
                        if ln.lower().startswith("- company:")), "")
        if not company and text.startswith("# Company Core"):
            company = text.splitlines()[0].replace("# Company Core", "").strip(" —-")
        marker.write_text(
            f"onboarded: {datetime.now(timezone.utc).date().isoformat()}\n"
            f"company: {company}\nvia: migrate\n", encoding="utf-8")
    return True


def stale_jobs(target: Path) -> List[str]:
    """launchd jobs pointing anywhere other than the live profile."""
    out: List[str] = []
    la = Path.home() / "Library" / "LaunchAgents"
    for plist in la.glob("*ernest*.plist") if la.is_dir() else []:
        try:
            data = plistlib.loads(plist.read_bytes())
        except Exception:  # noqa: BLE001
            continue
        args = " ".join(a for a in data.get("ProgramArguments", []) if isinstance(a, str))
        if str(target) not in args:
            out.append(str(plist))
    return out


def unload_stale(target: Path, dry: bool = False) -> List[str]:
    removed = []
    for plist in stale_jobs(target):
        if not dry:
            subprocess.run(["launchctl", "unload", plist], capture_output=True)
            try:
                Path(plist).unlink()
            except OSError:
                continue
        removed.append(plist)
    return removed


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Adopt an earlier Ernest install")
    ap.add_argument("--target", default=os.environ.get("ERNEST_PROFILE_DIR",
                                                       str(Path.home() / ".ernest-cc")))
    ap.add_argument("--from", dest="source", help="adopt this profile specifically")
    ap.add_argument("--discover", action="store_true", help="list what is out there")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    target = Path(args.target).expanduser().resolve()

    if args.discover:
        found = discover(target)
        if args.json:
            print(json.dumps({"target": str(target), "candidates": found}, indent=2))
        else:
            if not found:
                print("No Ernest profile found anywhere.")
            for c in found:
                tag = " (this one)" if c["is_target"] else ""
                world = "SAMPLE world" if c["sample_world"] else c["company"]
                print(f"  {c['path']}{tag}\n      {world} · "
                      f"{'onboarded' if c['onboarded'] else 'not onboarded'} · "
                      f"{len(c['has'])} adoptable item(s)")
        return 0

    source = Path(args.source).expanduser().resolve() if args.source else None
    if source is None:
        pick = best_source(target)
        if pick is None:
            msg = {"ok": True, "adopted": [], "why": "no earlier install found"}
            print(json.dumps(msg, indent=2) if args.json else "Nothing to migrate.")
            return 0
        source = Path(pick["path"])

    res = migrate(target, source, dry=args.dry_run)
    res["stale_jobs"] = unload_stale(target, dry=args.dry_run)
    if args.json:
        print(json.dumps(res, indent=2))
    elif not res["ok"]:
        print(f"Migrate: {res['why']}", file=sys.stderr)
    else:
        verb = "Would adopt" if args.dry_run else "Adopted"
        print(f"{verb} from {res['source']}:")
        for a in res["adopted"] or []:
            note = f" ({a['note']})" if a.get("note") else ""
            print(f"  - {a['what']}: {a['count']} — {a['why']}{note}")
        if not res["adopted"]:
            print("  (nothing new — already up to date)")
        if res["stale_jobs"]:
            print(f"  - removed {len(res['stale_jobs'])} stale scheduled job(s)")
        if res.get("backup"):
            print(f"  backup: {res['backup']}")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
