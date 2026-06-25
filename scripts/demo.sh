#!/usr/bin/env bash
# End-to-end demo on bundled sample data. No install, model, connectors, or network.
#   ./scripts/demo.sh
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

step "1. Start (watch + brief)"
ernest start

step "2. Optional onboard"
ernest onboard --non-interactive --name "CEO" --role "CEO" --company "Acme Inc"

step "3. Draft (optional)"
ernest draft --concern dropped-followups

step "4. Scale: new automation"
ernest new-automation --id investor-followups \
  --playbook account-followup-recovery --staleness 5d \
  --description "Weekly investor follow-up check"

step "5. Self-improve: learn -> adopt"
ernest learn --note "CEO keeps checking partner renewals every Monday."
ernest learn --adopt 1 --id partner-renewals \
  --playbook account-followup-recovery --staleness 7d
ernest start

step "Artifacts"
find "$VAULT/Ernest" -type f | sort
printf '\nSandbox: rm -rf %s\n' "$SANDBOX"
