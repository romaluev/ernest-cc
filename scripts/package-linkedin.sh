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
VERSION="${LI_BUNDLE_VERSION:-2.1.0}"
OUT="$ROOT/dist"
SEED=""
while [ $# -gt 0 ]; do
  case "$1" in
    --out) shift; OUT="${1:-$OUT}" ;;
    # Bake a real rubric/identity into the zip so the recipient needs nothing
    # else. Use for a private handover; never for anything published.
    --seed) shift; SEED="${1:-}" ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown flag $1" >&2; exit 2 ;;
  esac
  shift
done

NAME="linkedin-inbound-$VERSION"
SUFFIX=""
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

if [ -n "$SEED" ] && [ -d "$SEED" ]; then
  [ -d "$SEED/data/grading" ] && cp "$SEED/data/grading"/*.json "$STAGE/data/grading/" 2>/dev/null
  [ -d "$SEED/memory" ] && mkdir -p "$STAGE/memory" && cp "$SEED/memory"/*.md "$STAGE/memory/" 2>/dev/null
  say "seeded with the real rubric and identity from $SEED"
  SUFFIX="-private"
fi

BUILD_SHA="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
BUILD_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
cat > "$STAGE/BUILD.txt" <<EOF
linkedin-inbound $VERSION${SUFFIX:-}
built: $BUILD_AT
commit: $BUILD_SHA
seeded: $([ -n "$SEED" ] && echo yes || echo "no (sample data)")
EOF
say "build stamp: $VERSION${SUFFIX:-} @ $BUILD_SHA"

python3 "$ROOT/scripts/package_linkedin_files.py" "$STAGE" "$VERSION"
say "README (human), AGENTS.md (agent), install.sh, cron, engine shim"

echo
echo "Verifying the bundle before packaging it..."
VERIFY_FAIL=0
( cd "$STAGE" && python3 linkedin_triage.py --grade-only >/dev/null 2>&1 ) \
  || { echo "  FAIL: the bundle cannot produce a report" >&2; VERIFY_FAIL=1; }
for want in linkedin-invitations linkedin-dms; do
  if ls "$STAGE"/reports/Ernest/00-Watch/$want--*.md >/dev/null 2>&1; then
    say "$want report produced"
  else
    echo "  FAIL: no $want report — that half of the bundle is dead" >&2
    VERIFY_FAIL=1
  fi
done
for t in "$STAGE"/tests/test_*.py; do
  ( cd "$STAGE" && PYTHONPATH="$STAGE" python3 "$t" >/dev/null 2>&1 ) \
    && say "$(basename "$t" .py) passes" \
    || { echo "  FAIL: $(basename "$t")" >&2; VERIFY_FAIL=1; }
done
# Every name the entry point calls must actually exist in the shipped engine.
python3 - "$STAGE" <<'PYCHK' || VERIFY_FAIL=1
import ast, pathlib, sys
stage = pathlib.Path(sys.argv[1])
src = (stage / "ernest" / "grade_run.py").read_text()
tree = ast.parse(src)
defined = {n.name for n in ast.walk(tree)
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
called = {n.func.id for n in ast.walk(tree)
          if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
import builtins
missing = sorted(c for c in called
                 if c not in defined and not hasattr(builtins, c)
                 and c not in {"Config", "Path", "Grade", "LinkedInGrade", "LinkedInDMGrade",
                               "Invitation", "Conversation", "Contact", "dc_field",
                               "load_contacts", "load_threads", "load_invitations",
                               "load_conversations", "grade_b2b", "grade_talent",
                               "grade_linkedin_inbound", "grade_linkedin_dm",
                               "pool_name", "ensure_dirs", "dataclass", "field"})
if missing:
    print(f"  FAIL: grade_run.py calls names that do not ship: {missing}", file=sys.stderr)
    sys.exit(1)
print("  [ok] every function the engine calls is present")
PYCHK
rm -rf "$STAGE/reports" "$STAGE/logs" "$STAGE/data/linkedin/.ingest.json"
if [ "$VERIFY_FAIL" -ne 0 ]; then
  echo >&2
  echo "REFUSING to package a broken bundle. Fix the failures above." >&2
  rm -rf "$(dirname "$STAGE")"
  exit 1
fi
echo

mkdir -p "$OUT"
ZIP="$OUT/$NAME${SUFFIX:-}.zip"
rm -f "$ZIP"
( cd "$(dirname "$STAGE")" && zip -qr "$ZIP" "$NAME" -x '*__pycache__*' '*.pyc' )
rm -rf "$(dirname "$STAGE")"

echo
echo "Built $ZIP ($(du -h "$ZIP" | cut -f1))"
echo "Hand it over as-is. The recipient runs: unzip, then ./install.sh"
