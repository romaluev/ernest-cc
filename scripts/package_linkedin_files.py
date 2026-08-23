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
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main() -> int:
    ap = argparse.ArgumentParser(description="LinkedIn inbound triage")
    ap.add_argument("--grade-only", action="store_true", help="skip the ingest step")
    ap.add_argument("--from-archive", help="a downloaded LinkedIn export .zip")
    args = ap.parse_args()

    os.environ.setdefault("ERNEST_PROFILE_DIR", str(HERE))
    os.environ.setdefault("ERNEST_LOCAL_VAULT", str(HERE / "reports"))
    os.environ.setdefault("ERNEST_MODE", "local")

    if not args.grade_only:
        cmd = [sys.executable, str(HERE / "adapters" / "linkedin" / "ingest.py"),
               "--profile-dir", str(HERE)]
        if args.from_archive:
            cmd += ["--from-archive", args.from_archive]
        proc = subprocess.run(cmd, text=True)
        if proc.returncode not in (0,):
            print("\\nIngest could not reach LinkedIn. Grading whatever is already here.",
                  file=sys.stderr)

    from ernest import config, grade_run          # noqa: E402
    cfg = config.load()
    written = grade_run.run(cfg, b2b=False, talent=False, linkedin=True)
    if not written:
        print("Nothing to grade. Run the ingest first, or drop a CSV into data/linkedin/.")
        return 3
    for path in written:
        print(path)
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
#   ./install.sh              install, verify, run once, schedule
#   ./install.sh --no-cron    skip the daily schedule
#
# No pip, no npm, no vendor SDK. Python standard library only.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DO_CRON=1
[ "${1:-}" = "--no-cron" ] && DO_CRON=0

GAPS=()
step() { printf '  [%s] %s\\n' "$1" "$2"; }
gap()  { GAPS+=("$1"); }

echo ""; echo "LinkedIn inbound triage — setup"; echo "==============================="

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

if python3 "$HERE/linkedin_triage.py" --grade-only >/dev/null 2>&1; then
  step ok "graded the sample queue — reports/ written"
else
  step "--" "could not produce a report yet"
  gap "Run \\`python3 linkedin_triage.py\\` and read the error."
fi

for t in "$HERE"/tests/test_*.py; do
  [ -e "$t" ] || continue
  PYTHONPATH="$HERE" python3 "$t" >/dev/null 2>&1 \\
    && step ok "$(basename "$t" .py) passes" \\
    || { step "--" "$(basename "$t" .py) FAILED"; gap "A guarantee is broken: PYTHONPATH=$HERE python3 $t"; }
done

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
  echo "Ready. Reports land in reports/Ernest/00-Watch/."
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
write("README.md", f'''# LinkedIn inbound triage — v{VERSION}

Turn thousands of pending LinkedIn connection invitations into a page you act on
in two minutes, without accepting a competitor, ignoring a journalist, or
reporting a customer as spam.

**It reports. It does not act.** Accepting, ignoring, and reporting only happen
after you approve a batch that names every person in it.

## Setup

```bash
unzip linkedin-inbound-{VERSION}.zip
cd linkedin-inbound-{VERSION}
./install.sh
```

That checks Python, finds a way to reach LinkedIn, produces a first report, runs
the tests, and schedules a daily 08:00 run. It prints exactly what is still
missing rather than claiming success.

Python 3.9+ is the only requirement. No pip, no npm, no accounts, no
subscriptions, no data leaves your machine.

## Getting your invitations in

It tries several ways and tells you which one worked:

1. **A file you already have** — anything in `data/linkedin/`.
2. **LinkedIn's own data export** *(easiest, nothing to install)* — Settings →
   Data Privacy → Get a copy of your data → tick **Invitations**. It arrives in
   minutes. Then:
   ```bash
   python3 linkedin_triage.py --from-archive ~/Downloads/*.zip
   ```
3. **Your live LinkedIn tab** — start Chrome with remote debugging on the profile
   you are signed in with:
   ```bash
   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \\
     --remote-debugging-port=9222 --profile-directory=Default
   ```

If none of them work it says so and tells you how to fix it. **It never invents a
number.** An empty answer and "I could not check" are different things here.

## Reading the report

Reports land in `reports/Ernest/00-Watch/`. A `.md` you read and a `.csv` with
everyone in it.

| On the report | Means |
|---|---|
| `[TIER-1]` | Worth your time. Matches who actually buys from you. |
| `[HOLD]` | Press, investors, competitors, legal. **Never auto-resolved.** |
| `[BUCKET] Worth a look` | ICP-adjacent, no decisive signal. Skim the CSV. |
| `[BUCKET] Spam / seller pitch` | Cold vendor and mass-template invites. |
| `source:` | Which method produced this data — a month-old export and a live read never look alike. |

## Clearing the spam

```bash
python3 adapters/linkedin/act.py --caps                  # what is left today
python3 adapters/linkedin/act.py --plan --tier trash     # writes a batch file
# open the batch, delete anyone who does not belong, then:
python3 adapters/linkedin/act.py --execute <batch.json>
```

Nothing happens until you run `--execute`, and even then it is a dry run until
you set `dry_run: false` and `approved: true` in `ernest.yaml`.

Daily caps (25 accepts, 100 ignores) exist because sudden mass action is what
gets LinkedIn accounts restricted — steady action does not.

**Reporting someone as spam cannot be undone** and affects their account, so it
always needs an explicit named list, every single run.

## Teaching it

When it gets someone wrong:

```bash
python3 adapters/linkedin/act.py --rescue slug:their-name --actual tier-1 --why "real customer"
```

Three corrections of the same shape and it proposes a rubric change you can
review and undo. It never changes its own scoring silently.

## Making it yours

`data/grading/linkedin-rubric.json` is the whole scoring brain, and it ships with
sample lists. Edit them:

- `tier1.buyer_archetypes` / `verticals` — who actually buys from you. Derive
  these from closed-won revenue, not from a targeting deck; the two disagree
  more often than not.
- `hold.competitor_keywords` — your competitors.
- `spam.threshold` — raise it if real people land in the spam bucket.

**Edit the lists; never delete a key.** The file replaces built-in defaults
wholesale, so a missing key turns that whole signal family off silently.

## Trust

- Reports first, acts only on an approved named batch.
- Never fabricates a population; says which source answered.
- Blank is not zero — a field it could not see never counts as evidence.
- Runs entirely on your machine. Standard library only.
- `tests/` asserts all of the above; `./install.sh` runs them.

For agents: read `AGENTS.md`.
''')

# --------------------------------------------------------------------------- #
# Agent brief
# --------------------------------------------------------------------------- #
write("AGENTS.md", f'''# Read this first (you are an agent setting this up)

Someone handed you `linkedin-inbound-{VERSION}.zip` and asked you to install it.
This file is the whole brief.

**Do not improvise.** Run `./install.sh` and act on what it reports.

## What this is

Standalone LinkedIn inbound triage. It grades pending connection invitations
against an ICP rubric, separates spam from people the principal simply cannot
place, holds press/investors/competitors for a human, and writes one report.

It **reports**. Accepting, ignoring, and reporting spam happen only through an
approved batch that names every person.

| Path | What |
|---|---|
| `linkedin_triage.py` | entry point: ingest + grade + report |
| `adapters/linkedin/` | ingest ladder, browser drivers, act layer, DOM notes |
| `skills/linkedin-invitations/` | the full skill — read it before doing this by hand |
| `ernest/` | the grading subset; do not edit |
| `data/grading/linkedin-rubric.json` | the scoring brain — lists only |
| `reports/` | output |
| `tests/` | the guarantees |

Python 3.9+, standard library only. **Never add a dependency**; the constraint is
deliberate.

## Setup

```bash
./install.sh                 # verify, first report, tests, daily 08:00 schedule
./install.sh --no-cron       # skip the schedule
```

Exit `0` ready · `1` ready with gaps (each gap names its fix) · `10`
unrecoverable — stop and report it.

## Decide yourself vs. ask

Decide: the daily schedule (read-only, removable), which ingest rung to use (the
ladder picks; you report which answered), and keeping everything local.

Ask once, plainly: how to reach their LinkedIn if no rung is reachable — the data
export is the easiest answer and needs nothing installed. And before any first
batch, confirm they have read it.

## Rules

- **Never fabricate a population.** If no rung reaches LinkedIn, say so and give
  the remedy. "Nothing pending" and "I could not check" are different answers.
- **Provenance rides through.** Always say which source produced the report. A
  month-old export must never be presented as live.
- **Missing is not zero.** A field a rung cannot see stays blank and scores
  nothing. The archive rung carries no mutual-connection count, so it
  under-detects spam by design — that is the correct trade.
- **Never act on a category.** Batches name people. A batch with no names is
  refused, and so is any tier that landed in `hold`.
- **Reporting spam is irreversible** and affects the other account. It needs an
  explicit named list every run and never becomes automatic.
- **Do not over-trash.** An ambiguous stranger is tier-2 with a flag, not spam.
  Missing spam costs a scroll; wrongly reporting a customer cannot be undone.

## Verify

```bash
python3 adapters/linkedin/ingest.py --doctor    # rungs_reachable must be non-empty
python3 linkedin_triage.py                      # writes reports/Ernest/00-Watch/
for t in tests/test_*.py; do PYTHONPATH=$PWD python3 "$t"; done
```

Exit codes shared by both CLIs: `0` ok · `2` usage · `3` nothing to work on ·
`4` unreachable · `5` upstream · `6` refused by policy · `7` rate limited ·
`10` config. Both answer in a provenance envelope
`{{"meta": {{"source", "rung", "synced_at"}}, "results": {{...}}}}`; `--agent`
implies `--json --compact` and never prompts.

## When the DOM changes

LinkedIn ships UI changes without notice. `adapters/linkedin/references/dom-notes.md`
holds the selectors and the known traps — read it before changing a selector, and
**append what you learn**. That file is the memory this has instead of a test
against a live site.

## Tuning

`data/grading/linkedin-rubric.json` is the scoring brain and ships with sample
lists. Edit lists, **never delete keys** — the file replaces built-in defaults
wholesale, so a missing key silently disables a whole signal family.

Corrections: `act.py --rescue <key> --actual <tier> --why "..."`. Three of the
same shape produce a reviewable rubric proposal. Nothing changes silently.
''')

# --------------------------------------------------------------------------- #
# Standalone policy file
# --------------------------------------------------------------------------- #
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
