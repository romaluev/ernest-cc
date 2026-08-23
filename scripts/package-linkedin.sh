#!/usr/bin/env bash
# Build a standalone, giveable LinkedIn inbound triage bundle.
#
# The point: hand someone a single zip. They (or their agent) unzip it, run one
# command, and have a working, scheduled, self-maintaining LinkedIn triage —
# without cloning this repo, without the rest of Ernest, and without installing
# anything from pip or npm.
#
#   ./scripts/package-linkedin.sh              -> dist/linkedin-inbound-<ver>.zip
#   ./scripts/package-linkedin.sh --out /tmp   -> somewhere else
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${LI_BUNDLE_VERSION:-2.0.0}"
OUT="$ROOT/dist"
while [ $# -gt 0 ]; do
  case "$1" in
    --out) shift; OUT="${1:-$OUT}" ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown flag $1" >&2; exit 2 ;;
  esac
  shift
done

NAME="linkedin-inbound-$VERSION"
STAGE="$(mktemp -d)/$NAME"
mkdir -p "$STAGE"

say() { printf '  %s\n' "$*"; }
echo "Packaging $NAME"

# --- the skill, verbatim ----------------------------------------------------
mkdir -p "$STAGE/skills"
cp -R "$ROOT/skills/linkedin-invitations" "$STAGE/skills/"
cp -R "$ROOT/skills/linkedin-inbox" "$STAGE/skills/"
say "both skills (invitations + inbox) with the rubric reference"

# --- the adapter ------------------------------------------------------------
mkdir -p "$STAGE/adapters/linkedin"
cp "$ROOT/adapters/linkedin"/*.py "$STAGE/adapters/linkedin/"
cp "$ROOT/adapters/linkedin/README.md" "$STAGE/adapters/linkedin/"
cp -R "$ROOT/adapters/linkedin/references" "$STAGE/adapters/linkedin/"
say "ingest ladder, browser drivers, act layer, DOM notes"

# --- the engine subset it actually needs ------------------------------------
# Only what grading touches. The bundle must run without the rest of Ernest.
mkdir -p "$STAGE/ernest"
for f in __init__.py config.py grading.py sources.py grade_run.py li_insight.py; do
  cp "$ROOT/ernest/$f" "$STAGE/ernest/$f"
done
cat > "$STAGE/ernest/README.md" <<'EOF'
Grading subset of the Ernest engine, shipped so this bundle runs on its own.
Standard library only. Do not edit — tune `data/grading/linkedin-rubric.json`
instead. The full product lives in the ernest-cc repo.
EOF
mkdir -p "$STAGE/data/grading" "$STAGE/data/linkedin"
cp "$ROOT/data/grading/linkedin-rubric.json" "$STAGE/data/grading/"
cp "$ROOT/data/linkedin/invitations.csv" "$STAGE/data/linkedin/"
cp "$ROOT/data/linkedin/messages.csv" "$STAGE/data/linkedin/"
mkdir -p "$STAGE/data/hubspot"
cp "$ROOT/data/hubspot/sample-contacts.csv" "$STAGE/data/hubspot/"
say "grading + insight engine, sample invitations, DMs and CRM facts"

# --- tests, so a recipient can verify the guarantees themselves --------------
mkdir -p "$STAGE/tests/fixtures"
cp "$ROOT/tests/test_linkedin_grading.py" "$ROOT/tests/test_linkedin_ingest.py" \
   "$ROOT/tests/test_linkedin_actions.py" "$ROOT/tests/test_linkedin_insight.py" \
   "$ROOT/tests/test_linkedin_browser.py" "$STAGE/tests/"
cp "$ROOT/tests/fixtures/linkedin-archive.zip" "$STAGE/tests/fixtures/" 2>/dev/null || true
say "tests"

# --- docs -------------------------------------------------------------------
mkdir -p "$STAGE/docs"
cp "$ROOT/docs/ingest-ladder.md" "$ROOT/docs/linkedin-spec.md" "$STAGE/docs/"
say "docs: the ingest ladder and the full decision spec"

python3 "$ROOT/scripts/package_linkedin_files.py" "$STAGE" "$VERSION"
say "README (human), AGENTS.md (agent), install.sh, cron, engine shim"

mkdir -p "$OUT"
ZIP="$OUT/$NAME.zip"
rm -f "$ZIP"
( cd "$(dirname "$STAGE")" && zip -qr "$ZIP" "$NAME" -x '*__pycache__*' '*.pyc' )
rm -rf "$(dirname "$STAGE")"

echo
echo "Built $ZIP ($(du -h "$ZIP" | cut -f1))"
echo "Hand it over as-is. The recipient runs: unzip, then ./install.sh"
