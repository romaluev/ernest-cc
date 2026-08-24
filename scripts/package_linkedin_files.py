#!/usr/bin/env python3
"""Write the standalone bundle's own entry points.

Kept out of package-linkedin.sh so these files are readable as files rather than
as heredocs inside heredocs.
"""
from __future__ import annotations

import stat
import sys
from pathlib import Path

STAGE = Path(sys.argv[1])
VERSION = sys.argv[2] if len(sys.argv) > 2 else "1.0.0"


def write(rel: str, text: str, execute: bool = False) -> None:
    path = STAGE / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if execute:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


# --------------------------------------------------------------------------- #
# A shim so the copied engine subset imports as `ernest.*` without the rest of it
# --------------------------------------------------------------------------- #
write("linkedin_triage.py", '''#!/usr/bin/env python3
"""Standalone entry point: triage invitations AND DMs, and write both reports.

The bundle carries the grading subset of the Ernest engine under `ernest/`, so
the same grading path the full product runs works here unchanged — and so the
bundled tests are runnable, which is half of why any of this is trustworthy.

    python3 linkedin_triage.py                # ingest (if stale) + grade + report
    python3 linkedin_triage.py --grade-only   # grade whatever is already here
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


_NICE_NAMES = {"linkedin-invitations": "invitations", "linkedin-dms": "messages"}


def reports_root() -> Path:
    """Where a human will actually go looking.

    Same convention as the /last30days skill: ~/Documents/<Name>, overridable
    with an env var, created on demand. Burying reports inside the install
    directory means nobody reads them.
    """
    override = os.environ.get("LI_REPORTS_DIR", "").strip()
    root = Path(override).expanduser() if override else (
        Path.home() / "Documents" / "LinkedIn-Inbound")
    root.mkdir(parents=True, exist_ok=True)
    return root


def find_export() -> Optional[Path]:
    """The most recent LinkedIn export sitting in the usual places.

    Asking someone to "drop the zip here or tell me where it landed" is asking
    them to do the one bit of work a computer is good at.
    """
    seen = []
    for folder in (Path.home() / "Downloads", Path.home() / "Desktop", Path.cwd()):
        if not folder.is_dir():
            continue
        for p in folder.glob("*.zip"):
            name = p.name.lower()
            if "linkedin" in name or "basic_linkedindataexport" in name or "complete_" in name:
                seen.append(p)
    return max(seen, key=lambda p: p.stat().st_mtime) if seen else None


def _tidy(written, source_root: Path, dest: Path, *, point_latest: bool = True):
    """Copy the engine's output into a layout a human can navigate.

    The engine nests reports under <vault>/Ernest/00-Watch/ with the date in the
    filename, which makes sense inside the larger product and makes none here.
    Standalone it should be reports/<date>/invitations.md — obvious, sorted, and
    with a `latest` that always points at the newest run.
    """
    import shutil
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for path in written:
        path = Path(path)
        stem = path.stem.split("--")[0]
        nice = _NICE_NAMES.get(stem, stem)
        target = dest / f"{nice}{path.suffix}"
        shutil.copy2(path, target)
        out.append(target)
    if not point_latest:
        return out
    latest = dest.parent / "latest"
    try:
        if latest.is_symlink() or latest.exists():
            latest.unlink() if latest.is_symlink() else shutil.rmtree(latest)
        latest.symlink_to(dest.name)
    except OSError:
        pass                      # a pointer is a convenience, not a requirement
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="LinkedIn inbound triage")
    ap.add_argument("--grade-only", action="store_true", help="skip the ingest step")
    ap.add_argument("--from-archive", help="a downloaded LinkedIn export .zip")
    ap.add_argument("--demo", action="store_true",
                    help="run against the fictional examples in a scratch dir")
    args = ap.parse_args()

    if args.demo:
        import shutil
        # Inside the install, and reused. Scattering scratch directories around
        # someone's machine is not an acceptable side effect of a demo.
        scratch = HERE / ".demo"
        if scratch.exists():
            shutil.rmtree(scratch, ignore_errors=True)
        for sub in ("data/grading", "data/linkedin", "data/hubspot", "memory"):
            (scratch / sub).mkdir(parents=True, exist_ok=True)
        for src, dst in ((HERE / "examples" / "invitations.example.csv",
                          scratch / "data" / "linkedin" / "invitations.csv"),
                         (HERE / "examples" / "messages.example.csv",
                          scratch / "data" / "linkedin" / "messages.csv"),
                         (HERE / "examples" / "contacts.example.csv",
                          scratch / "data" / "hubspot" / "contacts.csv")):
            if src.is_file():
                shutil.copy(src, dst)
        for src in (HERE / "data" / "grading").glob("*.json"):
            shutil.copy(src, scratch / "data" / "grading" / src.name)
        for src in (HERE / "memory").glob("*.md"):
            shutil.copy(src, scratch / "memory" / src.name)
        os.environ["ERNEST_PROFILE_DIR"] = str(scratch)
        os.environ["ERNEST_LOCAL_VAULT"] = str(scratch / "reports")
        os.environ["ERNEST_MODE"] = "local"
        sys.path.insert(0, str(HERE))
        from ernest import config, grade_run      # noqa: E402
        written = grade_run.run(config.load(), b2b=False, talent=False,
                                linkedin=True, linkedin_dms=True)
        # A demo must never claim to be the latest real report.
        for path in _tidy(written, scratch, reports_root() / "demo",
                          point_latest=False):
            print(path)
        print("")
        print("Demo only — fictional people. Your own data/ was not touched.")
        return 0 if written else 3

    os.environ.setdefault("ERNEST_PROFILE_DIR", str(HERE))
    # A seeded bundle ships memory/ceo-persona.md next to this file; the engine
    # reads <profile>/memory, and the profile IS this directory, so it is picked
    # up with no extra wiring. That file pins the account owner, which decides
    # the direction of every message in the inbox.
    os.environ.setdefault("ERNEST_LOCAL_VAULT", str(HERE / ".state"))
    os.environ.setdefault("ERNEST_MODE", "local")

    have_data = any((HERE / "data" / "linkedin").glob("*.csv"))
    if not have_data and not args.from_archive:
        found = find_export()
        if found:
            print(f"Found a LinkedIn export already on this machine: {found}",
                  file=sys.stderr)
            args.from_archive = str(found)

    # ALWAYS run the ladder before saying anything is missing. The earlier
    # version printed a four-step "go and export your data" list whenever
    # data/linkedin was empty — which is exactly the state a fresh install is
    # in, so the very first run handed the user homework the tool can do
    # itself. The ladder requests the export, waits for it, downloads it and
    # unpacks it. The only thing it cannot do is type a password.
    if not args.grade_only:
        cmd = [sys.executable, str(HERE / "adapters" / "linkedin" / "ingest.py"),
               "--profile-dir", str(HERE)]
        if args.from_archive:
            cmd += ["--from-archive", args.from_archive]
        proc = subprocess.run(cmd, text=True)
        have_data = any((HERE / "data" / "linkedin").glob("*.csv"))
        if proc.returncode != 0 and not have_data:
            for line in [
                "",
                "Could not reach LinkedIn, and there is no cached data to fall back on.",
                "Nothing was invented — an empty report would be worse than none.",
                "",
                "In order, this is what was tried and what would unblock it:",
                "  - a cached export in data/linkedin/          (nothing there yet)",
                "  - requesting the export through the browser  (needs you signed in)",
                "  - reading the invitation manager live        (same)",
                "  - a HubSpot mirror                           (no export configured)",
                "",
                "Re-run this in a terminal you are watching and a browser window will",
                "open on the LinkedIn sign-in page; sign in once and the rest is",
                "automatic from then on, including on a schedule.",
                "",
                "Or, if the export mail has already landed:",
                "  python3 linkedin_triage.py --from-archive ~/Downloads/<the>.zip",
                "",
                "To see the shape of the report first, with fictional people:",
                "  python3 linkedin_triage.py --demo",
            ]:
                print(line, file=sys.stderr)
            return 3
        if proc.returncode != 0:
            print("Ingest could not refresh. Grading the data already here.",
                  file=sys.stderr)

    from ernest import config, grade_run          # noqa: E402
    cfg = config.load()
    # BOTH surfaces. Leaving linkedin_dms off here once shipped a bundle where
    # the DM half only ever ran in --demo — the exact failure this comment exists
    # to prevent recurring.
    written = grade_run.run(cfg, b2b=False, talent=False,
                            linkedin=True, linkedin_dms=True)
    if not written:
        print("Nothing to grade. Run the ingest first, or drop a CSV into data/linkedin/.")
        return 3
    stamp = datetime.now().strftime("%Y-%m-%d")
    dest = reports_root() / stamp
    out = _tidy(written, HERE, dest)
    for path in out:
        print(path)

    # Reply briefs for whoever is actually waiting.
    sys.path.insert(0, str(HERE / "adapters" / "linkedin"))
    try:
        import drafts as _drafts                              # noqa: E402
        from ernest import grade_run as _gr                   # noqa: E402
        analyzed = _gr.analyze_conversations(cfg)
        if analyzed:
            print(_drafts.write_drafts(cfg, analyzed, dest / "reply-briefs.md"))
    except Exception as exc:                                  # noqa: BLE001
        print(f"(could not write reply briefs: {exc})", file=sys.stderr)

    # A readable page, and a PDF when a browser is around to print one.
    try:
        import report as _report                              # noqa: E402
        page = _report.render_html(
            [("Invitations", dest / "invitations.md"),
             ("Messages", dest / "messages.md")],
            dest / "report.html")
        print(page)
        pdf = _report.render_pdf(page, dest / "report.pdf")
        if pdf:
            print(pdf)
    except Exception as exc:                                  # noqa: BLE001
        print(f"(could not render the HTML report: {exc})", file=sys.stderr)

    print("")
    print(f"Open: {reports_root() / 'latest'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''', execute=True)

# --------------------------------------------------------------------------- #
# Installer
# --------------------------------------------------------------------------- #
write("install.sh", '''#!/usr/bin/env bash
# One-command setup for the standalone LinkedIn inbound triage bundle.
#
#   ./install.sh              install and verify (no system changes)
#   ./install.sh --daily      also add a daily 08:00 crontab entry
#
# No pip, no npm, no vendor SDK. Python standard library only.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Scheduling edits the user's crontab, so it is OPT-IN. Handing someone a tool
# that quietly installs a daily job is not acceptable, however useful it is.
DO_CRON=0
[ "${1:-}" = "--daily" ] && DO_CRON=1

GAPS=()
step() { printf '  [%s] %s\\n' "$1" "$2"; }
gap()  { GAPS+=("$1"); }

echo ""
if [ -f "$HERE/BUILD.txt" ]; then
  echo "LinkedIn inbound triage — $(sed -n 1p "$HERE/BUILD.txt")"
  sed -n '2,4p' "$HERE/BUILD.txt" | sed 's/^/  /'
else
  echo "LinkedIn inbound triage — setup"
fi
echo "==============================="

command -v python3 >/dev/null 2>&1 || { echo "python3 not found. Install Python 3.9+." >&2; exit 10; }
PYV="$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
python3 -c 'import sys;sys.exit(0 if sys.version_info>=(3,9) else 1)' \\
  || { echo "python3 $PYV is too old (need 3.9+)." >&2; exit 10; }
step ok "python3 $PYV"

chmod +x "$HERE/linkedin_triage.py" "$HERE/adapters/linkedin"/*.py 2>/dev/null || true

RUNGS="$(python3 "$HERE/adapters/linkedin/ingest.py" --profile-dir "$HERE" --doctor --json 2>/dev/null \\
  | python3 -c 'import json,sys
try: print(",".join(str(r) for r in json.load(sys.stdin)["results"]["rungs_reachable"]))
except Exception: print("")')"
if [ -n "$RUNGS" ]; then
  step ok "LinkedIn reachable via rung(s) $RUNGS"
else
  step "--" "no way to reach LinkedIn yet"
  gap "Start Chrome with --remote-debugging-port=9222 on the profile signed in to LinkedIn, OR download your data export (Settings -> Data Privacy -> Get a copy of your data -> tick Invitations) and run: python3 linkedin_triage.py --from-archive <zip>"
fi

# Prove the pipeline works using the fictional examples in a scratch directory.
# data/ ships empty on purpose, so this must never write a report into it.
DEMO_OUT="$(python3 "$HERE/linkedin_triage.py" --demo 2>&1)"
if printf '%s' "$DEMO_OUT" | grep -q "invitations.md"; then
  step ok "invitations pipeline verified (on the examples)"
else
  step "--" "the invitations pipeline produced nothing"
  gap "Run \\`python3 linkedin_triage.py --demo\\` and read the error."
fi
if printf '%s' "$DEMO_OUT" | grep -q "messages.md"; then
  step ok "DM pipeline verified (on the examples)"
else
  step "--" "the DM pipeline produced nothing"
  gap "Run \\`python3 linkedin_triage.py --demo\\` and read the error."
fi

if ls "$HERE"/data/linkedin/*.csv >/dev/null 2>&1; then
  step ok "your LinkedIn export is loaded"
else
  step "--" "no LinkedIn data yet (this is expected on a fresh install)"
  gap "Get your export: LinkedIn -> Settings -> Data Privacy -> Get a copy of your data -> tick Invitations and Messages. Then: python3 linkedin_triage.py --from-archive ~/Downloads/<file>.zip"
fi

for t in "$HERE"/tests/test_*.py; do
  [ -e "$t" ] || continue
  PYTHONPATH="$HERE" python3 "$t" >/dev/null 2>&1 \\
    && step ok "$(basename "$t" .py) passes" \\
    || { step "--" "$(basename "$t" .py) FAILED"; gap "A guarantee is broken: PYTHONPATH=$HERE python3 $t"; }
done

if [ "$DO_CRON" -eq 0 ]; then
  step ok "no schedule installed (run ./install.sh --daily if you want one)"
fi
if [ "$DO_CRON" -eq 1 ]; then
  LINE="0 8 * * 1-5 cd \\"$HERE\\" && python3 \\"$HERE/linkedin_triage.py\\" >> \\"$HERE/triage.log\\" 2>&1"
  if crontab -l 2>/dev/null | grep -Fq "$HERE/linkedin_triage.py"; then
    step ok "daily 08:00 job already scheduled"
  elif (crontab -l 2>/dev/null; echo "$LINE") | crontab - 2>/dev/null; then
    step ok "scheduled daily at 08:00 (remove with: crontab -e)"
  else
    step "--" "could not write crontab"
    gap "Add this line yourself with \\`crontab -e\\`: $LINE"
  fi
fi

echo ""
if [ "${#GAPS[@]}" -eq 0 ]; then
  echo "Ready. Reports land in reports/latest/ (invitations.md, messages.md)."
  echo "Nothing is ever accepted, ignored, or reported without your approval."
  exit 0
fi
echo "Ready, with ${#GAPS[@]} thing(s) still open:"
for g in "${GAPS[@]}"; do echo "  - $g"; done
exit 1
''', execute=True)

# --------------------------------------------------------------------------- #
# Human README
# --------------------------------------------------------------------------- #
# The two long-form documents live as real markdown files under
# scripts/bundle-docs/ rather than as string literals here. They are read by
# humans and by agents, they change often, and reviewing a 300-line docstring
# diff is how errors get through.
_DOCS = Path(__file__).resolve().parent / "bundle-docs"
for _name in ("README.md", "AGENTS.md"):
    write(_name, (_DOCS / _name).read_text(encoding="utf-8")
          .replace("__VERSION__", VERSION))
write("docs/cloud-rung.md", (_DOCS / "cloud-rung.md").read_text(encoding="utf-8"))


write("ernest.yaml", '''# Policy for the standalone LinkedIn triage bundle.
# Caps live here, not in code, so tuning one is a config change with a trail.

linkedin_policy:
  job_id: linkedin-inbound
  # Master switches. Acting for real needs BOTH: dry_run false AND approved true.
  dry_run: true
  approved: false
  auto_ingest: true
  max_named_on_card: 15
  caps_per_day:
    accept: 25
    ignore: 100
    report_spam: 25
  # Pacing is a safety property, not politeness. Sudden mass action is what gets
  # accounts restricted; steady action does not.
  min_action_interval_seconds: 20
  never_auto:
    - report_spam        # not reversible, and it affects the other account
    - reply
    - inmail
  ingest_max_age_hours: 20
  audit_log: "logs/linkedin-actions.log"
  decision_journal: "logs/linkedin-decisions.jsonl"
''')

print("  wrote bundle entry points")
