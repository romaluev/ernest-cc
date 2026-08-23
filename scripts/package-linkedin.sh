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

# The upstream repo is public and ships a deliberately fictional sample world
# ("Northwind", "NovaLabs", "Sam Rivera") that its own tests bind to. None of
# that should reach a private handover, where it just reads as a company nobody
# recognises. Scrub the bundled COPY; the repo keeps its fixtures.
python3 - "$STAGE" <<'PYSCRUB'
import pathlib, re, sys
stage = pathlib.Path(sys.argv[1])
swaps = [
    ('"current_company": ["northwind"],', '"current_company": ["__your-company__"],'),
    ('"investor_terms": ["northwind investor", "invested in northwind"],',
     '"investor_terms": ["__your-company__ investor"],'),
    ("against the ex-NovaLabs rubric.", "against the talent rubric."),
    ('("Sam Rivera. Role: CEO & Co-Founder, Northwind."), so keep only the',
     '("Jane Doe. Role: CEO & Co-Founder, Acme."), so keep only the'),
    ('"as discussed with alex", "alex suggested", "sam rivera"],',
     '"as discussed with alex", "alex suggested"],'),
    ('"pool": "ex-NovaLabs",', '"pool": "talent",'),
]
changed = []
for path in (stage / "ernest").glob("*.py"):
    text = original = path.read_text(encoding="utf-8")
    for old, new in swaps:
        text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
        changed.append(path.name)
print("  scrubbed sample-world names from: " + (", ".join(changed) or "nothing"))
PYSCRUB
mkdir -p "$STAGE/data/grading" "$STAGE/data/linkedin" "$STAGE/data/hubspot"
cp "$ROOT/data/grading/linkedin-rubric.json" "$STAGE/data/grading/"

# The fixtures go to examples/, NOT to data/. A bundle that ships fictional
# people produces a convincing report about people who do not exist, and the
# only tell is that the names end in "-sample". data/ starts empty on purpose.
mkdir -p "$STAGE/examples"
cp "$ROOT/data/linkedin/invitations.csv" "$STAGE/examples/invitations.example.csv"
cp "$ROOT/data/linkedin/messages.csv" "$STAGE/examples/messages.example.csv"
cp "$ROOT/data/hubspot/sample-contacts.csv" "$STAGE/examples/contacts.example.csv"
cat > "$STAGE/examples/README.md" <<'EOF'
# Examples — fictional, for testing only

These are invented people. They exist so `./install.sh` can prove the pipeline
works end to end before you trust it with anything real, and so you can see the
shape of the input files.

`python3 linkedin_triage.py --demo` runs against them in a scratch directory
without touching `data/`.

**Never copy them into `data/`.** A report about fictional people that looks
exactly like a real one is worse than no report.
EOF

cat > "$STAGE/data/linkedin/README.md" <<'EOF'
# Put your LinkedIn export here

Empty on purpose — this tool does not ship fake people.

1. LinkedIn -> Settings -> Data Privacy -> **Get a copy of your data**
2. Tick **Invitations** and **Messages** (not the whole archive; those two
   arrive in minutes rather than up to 24 hours)
3. When the email lands:

   ```
   python3 linkedin_triage.py --from-archive ~/Downloads/<the-file>.zip
   ```

That writes `invitations.csv` and `messages.csv` here and produces your first
real report. Everything after that is automatic.

Already have the CSVs? Drop them in as `invitations.csv` and `messages.csv`.
The column names from LinkedIn's export are understood as-is.
EOF

cat > "$STAGE/data/hubspot/README.md" <<'EOF'
# Optional: CRM facts

Drop a contacts export here as CSV and the scoring gets much sharper, because
facts outrank inference. Recognised columns:

    email,firstname,lastname,company,tier,last_touch,open_deal,won_revenue

`open_deal` (true/false) and `won_revenue` (a number) are what promote someone
to `critical`. Without this file everything is scored from what people wrote
about themselves, which is weaker and is reported as such.
EOF
say "engine + real rubric; data/ ships EMPTY (fixtures live in examples/)"

# --- tests, so a recipient can verify the guarantees themselves --------------
mkdir -p "$STAGE/tests/fixtures"
cp "$ROOT/tests/test_linkedin_grading.py" "$ROOT/tests/test_linkedin_ingest.py" \
   "$ROOT/tests/test_linkedin_actions.py" "$ROOT/tests/test_linkedin_insight.py" \
   "$ROOT/tests/test_linkedin_browser.py" "$ROOT/tests/test_linkedin_edges.py" \
   "$STAGE/tests/"
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
set +e
find "$STAGE" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
VERIFY_FAIL=0
DEMO_OUT="$( cd "$STAGE" && python3 linkedin_triage.py --demo 2>&1 )" || {
  echo "  FAIL: the bundle cannot produce a report" >&2
  printf '%s\n' "$DEMO_OUT" | tail -12 >&2
  VERIFY_FAIL=1
}
for want in linkedin-invitations linkedin-dms; do
  if printf '%s' "$DEMO_OUT" | grep -q "$want--"; then
    say "$want report produced"
  else
    echo "  FAIL: no $want report — that half of the bundle is dead" >&2
    VERIFY_FAIL=1
  fi
done
# data/ must ship EMPTY. Shipping fixtures as if they were real is the bug this
# whole change exists to prevent, so it is checked, not assumed.
if ls "$STAGE"/data/linkedin/*.csv >/dev/null 2>&1; then
  echo "  FAIL: data/linkedin ships CSVs — the bundle would report on fake people" >&2
  VERIFY_FAIL=1
else
  say "data/ ships empty (fixtures are in examples/)"
fi
# A seeded build must carry NO fictional identity. "Northwind" and friends are
# the shipped sample world; if any of it survives into a private handover, the
# seed did not fully apply and the report will quietly reference a company that
# does not exist.
# A first run with no data must explain itself and exit 3, not crash or lie.
# `set -e` would abort here on the exit code we are deliberately asserting.
rc=0
( cd "$STAGE" && python3 linkedin_triage.py >/dev/null 2>&1 ) || rc=$?
if [ "$rc" -eq 3 ]; then
  say "a first run with no data explains itself (exit 3)"
else
  echo "  FAIL: first run with no data exited $rc, expected 3" >&2
  VERIFY_FAIL=1
fi
for t in "$STAGE"/tests/test_*.py; do
  ( cd "$STAGE" && PYTHONPATH="$STAGE" python3 "$t" >/dev/null 2>&1 ) \
    && say "$(basename "$t" .py) passes" \
    || { echo "  FAIL: $(basename "$t")" >&2; VERIFY_FAIL=1; }
done
find "$STAGE" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
if [ -n "$SEED" ]; then
  PLACEHOLDERS="$(grep -ril -e 'northwind' -e 'novalabs' -e 'sam rivera' -e 'novaframe' \
      "$STAGE/memory" "$STAGE/data" "$STAGE/skills" "$STAGE/ernest" "$STAGE/docs" \
      "$STAGE/adapters" "$STAGE"/*.md 2>/dev/null || true)"
  if [ -n "$PLACEHOLDERS" ]; then
    echo "  FAIL: sample-world names survive the seed:" >&2
    printf '    %s\n' $PLACEHOLDERS >&2
    VERIFY_FAIL=1
  else
    say "no sample-world identity left (seed fully applied)"
  fi
fi

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
find "$STAGE" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
set -e
if [ "$VERIFY_FAIL" -ne 0 ]; then
  echo >&2
  echo "REFUSING to package a broken bundle. Fix the failures above." >&2
  echo "Staging kept for inspection: $STAGE" >&2
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
