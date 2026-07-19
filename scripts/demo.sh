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

step "6. Self-heal: break config on purpose -> doctor detects -> heal restores"
ernest doctor > /dev/null || true            # healthy audit takes last-good snapshots
printf '# broken\n```yaml\nconcerns: [oops\n' > "$PROFILE/memory/standing-concerns.md"
ernest doctor > /dev/null 2>&1 && echo "UNEXPECTED: corruption not detected" || \
  echo "doctor: BROKEN detected (watch reminders would be silently OFF)"
ernest heal --no-selftest
grep -q "partner-renewals" "$PROFILE/memory/standing-concerns.md" \
  && echo "heal: standing-concerns restored from last-good snapshot (adopted concern intact)"

step "7. Self-improve: corrections -> evidence-ranked proposal -> apply -> rollback"
ernest feedback "Acme Robotics was actually tier-1" > /dev/null
ernest feedback "again: Acme Robotics was actually tier-1" > /dev/null
ernest feedback "third time: Acme Robotics was actually tier-1" > /dev/null
ernest learn | sed -n '1,6p'
ernest learn --apply rubric-acme-robotics-tier-1 | sed -n '1,2p'
APPLIED_ID="$(python3 - <<'PY'
import json, os, pathlib
log = pathlib.Path(os.environ["ERNEST_PROFILE_DIR"]) / "logs" / "applied.jsonl"
entries = [json.loads(l) for l in log.read_text().splitlines() if l.strip()]
print(next(e["id"] for e in reversed(entries) if e["action"] == "apply"))
PY
)"
ernest learn --rollback "$APPLIED_ID"

step "8. Selftest (the promotion-gate canary)"
ernest selftest | tail -1

step "Artifacts"
find "$VAULT/Ernest" -type f | sort
printf '\nLoops log trail: %s\n' "$PROFILE/logs (usage.jsonl, repairs.jsonl, applied.jsonl, versions/, snapshots/)"
printf 'Sandbox: rm -rf %s\n' "$SANDBOX"
