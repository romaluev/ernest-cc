#!/usr/bin/env bash
# One-pass setup: install -> identity -> schedule -> connectors -> first run -> verify.
#
# Written to be driven by an AGENT that was handed a link and asked to "install
# this". Idempotent: safe to re-run at any point, from any partial state.
#
#   ./scripts/bootstrap.sh                    # install + schedule + verify
#   ./scripts/bootstrap.sh --seed <dir>       # ...and install a real identity
#   ./scripts/bootstrap.sh --migrate-from <dir>  # adopt a specific old profile
#   ./scripts/bootstrap.sh --no-migrate          # do not adopt anything
#   ./scripts/bootstrap.sh --no-schedule      # skip the daily jobs
#   ./scripts/bootstrap.sh --json             # machine-readable summary
#
# Exit codes: 0 ready · 1 ready with gaps (see `next_steps`) · 10 unrecoverable.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE_DIR="${ERNEST_PROFILE_DIR:-$HOME/.ernest-cc}"
SEED=""; DO_SCHEDULE=1; AS_JSON=0; MIGRATE_FROM=""
STEPS=(); GAPS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --seed) shift; SEED="${1:-}" ;;
    --migrate-from) shift; MIGRATE_FROM="${1:-}" ;;
    --no-migrate) MIGRATE_FROM="SKIP" ;;
    --no-schedule) DO_SCHEDULE=0 ;;
    --json) AS_JSON=1 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "bootstrap: unknown flag $1" >&2; exit 10 ;;
  esac
  shift
done

say()  { [ "$AS_JSON" -eq 1 ] || printf '%s\n' "$*"; }
step() { STEPS+=("$1|$2"); [ "$AS_JSON" -eq 1 ] || printf '  [%s] %s\n' "$1" "$2"; }
gap()  { GAPS+=("$1"); }
die()  { printf 'bootstrap: %s\n' "$1" >&2; exit 10; }

say ""; say "Ernest bootstrap"; say "================"

# --- 1. Prereqs -------------------------------------------------------------
command -v python3 >/dev/null 2>&1 || die "python3 not found. Install Python 3.9+ and re-run."
PYV="$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
python3 -c 'import sys;sys.exit(0 if sys.version_info>=(3,9) else 1)' \
  || die "python3 $PYV is too old (need 3.9+)."
step ok "python3 $PYV"

# --- 2. Install / refresh ---------------------------------------------------
# --no-run: the first brief comes later, after identity is seeded, so the CEO
# never sees a brief full of sample people.
if [ -x "$PROFILE_DIR/bin/ernest" ]; then
  "$ROOT/install.sh" --refresh --no-run >/dev/null 2>&1 \
    && step ok "profile refreshed at $PROFILE_DIR" \
    || die "install.sh --refresh failed. Run it directly to see why."
else
  "$ROOT/install.sh" --no-run >/dev/null 2>&1 \
    && step ok "installed to $PROFILE_DIR" \
    || die "install.sh failed. Run it directly to see why."
fi
ERNEST="$PROFILE_DIR/bin/ernest"
[ -x "$ERNEST" ] || die "no launcher at $ERNEST after install."

# --- 2b. Adopt an earlier install -------------------------------------------
# Someone who "already tried this once" has memory, tuned rubrics, custom skills,
# and learning history sitting in an older profile. install.sh preserves a
# profile IN PLACE; this catches the other case — a prior install at a different
# path. Additive, backed up first, and idempotent.
MIG_ARGS=(--target "$PROFILE_DIR" --json)
[ -n "$MIGRATE_FROM" ] && [ "$MIGRATE_FROM" != "SKIP" ] && MIG_ARGS+=(--from "$MIGRATE_FROM")
if [ "$MIGRATE_FROM" = "SKIP" ]; then
  MIG="0|"
else
MIG="$(ERNEST_PROFILE_DIR="$PROFILE_DIR" python3 "$ROOT/scripts/migrate.py" \
        "${MIG_ARGS[@]}" 2>/dev/null \
      | python3 -c 'import json,sys
try:
    d = json.load(sys.stdin)
    n = sum(a["count"] for a in d.get("adopted") or [])
    print(f"{n}|{d.get('"'"'source'"'"','"'"''"'"')}")
except Exception: print("0|")' )"
fi
MIG_N="${MIG%%|*}"; MIG_SRC="${MIG#*|}"
if [ "${MIG_N:-0}" -gt 0 ]; then
  step ok "adopted $MIG_N item(s) from the earlier install at $MIG_SRC"
else
  step ok "no earlier install to adopt"
fi

# --- 3. Identity ------------------------------------------------------------
# The repo ships a fictional sample world on purpose. Real identity lives in the
# profile, which refresh never overwrites.
if [ -n "$SEED" ]; then
  [ -d "$SEED" ] || die "seed directory not found: $SEED"
  "$ROOT/scripts/seed-profile.sh" "$SEED" >/dev/null 2>&1 \
    && step ok "identity seeded from $SEED" \
    || die "seeding failed. Run scripts/seed-profile.sh $SEED directly."
elif [ -f "$PROFILE_DIR/vault/.onboarded" ] \
  || [ -f "${ERNEST_LOCAL_VAULT:-$HOME/ErnestVault}/.onboarded" ]; then
  step ok "already onboarded"
else
  step "--" "not onboarded — still running on SAMPLE data"
  gap "Run \`ernest onboard\` (or re-run with --seed <dir>) so reports use the real company, not the sample world."
fi

# --- 4. Daily schedule ------------------------------------------------------
if [ "$DO_SCHEDULE" -eq 1 ]; then
  "$ERNEST" schedule >/dev/null 2>&1 \
    && step ok "daily jobs installed (brief 08:00, auto-update 07:30, connector refresh 07:45)" \
    || { step "--" "could not install the daily schedule"; gap "Run \`ernest schedule\` directly to see why."; }
else
  step "--" "schedule skipped (--no-schedule)"
fi

# --- 5. Connectors ----------------------------------------------------------
# Systems with no API use an ingest ladder (docs/ingest-ladder.md). Report which
# rungs answer; never pretend an unreachable source is empty.
LI_DOCTOR="$PROFILE_DIR/adapters/linkedin/ingest.py"
[ -f "$LI_DOCTOR" ] || LI_DOCTOR="$ROOT/adapters/linkedin/ingest.py"
if [ -f "$LI_DOCTOR" ]; then
  RUNGS="$(ERNEST_PROFILE_DIR="$PROFILE_DIR" python3 "$LI_DOCTOR" --doctor --json 2>/dev/null \
    | python3 -c 'import json,sys
try: print(",".join(str(r) for r in json.load(sys.stdin)["results"]["rungs_reachable"]))
except Exception: print("")' )"
  if [ -n "$RUNGS" ]; then
    step ok "LinkedIn ingest reachable via rung(s) $RUNGS"
    ERNEST_PROFILE_DIR="$PROFILE_DIR" python3 "$LI_DOCTOR" >/dev/null 2>&1 \
      && step ok "LinkedIn queue pulled" \
      || { step "--" "LinkedIn pull found nothing yet"; gap "Sign in to LinkedIn in the browser this runs against, then \`python3 adapters/linkedin/ingest.py\`."; }
  else
    step "--" "no LinkedIn rung reachable"
    gap "Start Chrome with --remote-debugging-port=9222 on the profile signed in to LinkedIn, or download the data export and run \`python3 adapters/linkedin/ingest.py --from-archive <zip>\`."
  fi
fi

# --- 6. First run -----------------------------------------------------------
if OUT="$("$ERNEST" start 2>&1)"; then
  step ok "first brief written"
  printf '%s' "$OUT" | grep -qi "SAMPLE data" \
    && gap "Reports are still using SAMPLE data — onboarding has not taken."
else
  step "--" "\`ernest start\` did not complete"
  gap "Run \`ernest start\` directly to see the error."
fi

# --- 7. Verify --------------------------------------------------------------
DOCTOR="$("$ERNEST" doctor 2>&1)"
BROKEN="$(printf '%s' "$DOCTOR" | grep -c '\[BROKEN\]' || true)"
if [ "${BROKEN:-0}" -gt 0 ]; then
  step "--" "$BROKEN broken check(s)"
  gap "Run \`ernest heal\`, then \`ernest doctor\`. If it persists, see skills/ernest-self-repair/SKILL.md."
else
  step ok "doctor: 0 broken"
fi

# --- Summary ----------------------------------------------------------------
STATUS=$([ "${#GAPS[@]}" -eq 0 ] && echo ready || echo ready-with-gaps)
if [ "$AS_JSON" -eq 1 ]; then
  python3 - "$STATUS" "$PROFILE_DIR" "${STEPS[@]:-}" <<'PY' 2>/dev/null || true
import json, sys
status, profile, *steps = sys.argv[1:]
print(json.dumps({"status": status, "profile": profile,
                  "steps": [{"ok": s.split("|",1)[0] == "ok", "what": s.split("|",1)[1]}
                            for s in steps if "|" in s]}, indent=2))
PY
  [ "${#GAPS[@]}" -eq 0 ] || printf '%s\n' "${GAPS[@]}" >&2
else
  say ""
  if [ "${#GAPS[@]}" -eq 0 ]; then
    say "Ready. Daily brief at 8:00; run \`ernest start\` any time."
    say "Nothing is ever sent, accepted, or deleted without your approval."
  else
    say "Ready, with ${#GAPS[@]} thing(s) still open:"
    for g in "${GAPS[@]}"; do say "  - $g"; done
  fi
fi
[ "${#GAPS[@]}" -eq 0 ] && exit 0 || exit 1
