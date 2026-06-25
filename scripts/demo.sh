#!/usr/bin/env bash
# Ernest end-to-end demo. Runs the whole lifecycle in a throwaway sandbox using
# the bundled sample data. No install, no model, no connectors, no network.
#
#   ./scripts/demo.sh
#
# It prints each step and the real artifacts produced (watch cards, brief,
# draft-only outreach), then shows the self-improvement loop (observe -> propose
# -> adopt -> live).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/ernest-demo.XXXXXX")"
PROFILE="$SANDBOX/profile"
VAULT="$SANDBOX/vault"
mkdir -p "$PROFILE"
cp -R "$ROOT/memory" "$PROFILE/memory"
cp -R "$ROOT/data" "$PROFILE/data"

export ERNEST_PROFILE_DIR="$PROFILE"
export ERNEST_LOCAL_VAULT="$VAULT"
export ERNEST_MODE="local"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1

ernest() { python3 -m ernest.cli "$@"; }
step() { printf '\n=== %s ===\n' "$1"; }

step "1. Health check"
ernest doctor

step "2. Onboard (non-interactive)"
ernest onboard --non-interactive --name "Sam Director" --role "CEO" \
  --company "UnicornCo" --icp "Series A-C B2B SaaS founders"

step "3. Ambient watch -> reminder cards"
ernest watch

step "4. Morning brief"
ernest brief

step "5. Draft-only outreach (never sends)"
ernest draft --concern dropped-followups

step "6. Scale: add a new automation by command"
ernest new-automation --id investor-followups \
  --playbook account-followup-recovery --staleness 5d \
  --description "Watch investor threads weekly"

step "7. Self-improvement: observe -> propose -> adopt -> live"
ernest learn --note "CEO keeps manually checking partner renewals every Monday."
ernest learn --adopt 1 --id partner-renewals \
  --playbook account-followup-recovery --staleness 7d
ernest watch

step "Artifacts produced"
find "$VAULT/Ernest" -type f | sort
printf '\nProfile: %s\nVault:   %s\n' "$PROFILE" "$VAULT"
printf 'Sandbox is disposable: rm -rf %s\n' "$SANDBOX"
