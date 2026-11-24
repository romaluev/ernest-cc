#!/usr/bin/env bash
# Seed a real Ernest profile from a seed directory.
#
# This repo ships a deliberately FICTIONAL sample world ("Northwind"), and the
# test suite binds to it. Real identity therefore never lands in the repo — it
# lands in the profile, which `install.sh --refresh` never overwrites.
#
#   scripts/seed-profile.sh /path/to/seed-dir
#
# The seed directory holds:
#   identity.env     NAME= ROLE= COMPANY= ICP= REDLINES=      (required)
#   memory/*.md      any memory files to install verbatim      (optional)
#   data/grading/*.json  rubric overrides                      (optional)
#
# Re-running is safe: `ernest onboard` backs memory up first, and on a profile
# that has already been onboarded it MERGES rather than clobbers.
set -euo pipefail

SEED="${1:-}"
PROFILE_DIR="${ERNEST_PROFILE_DIR:-$HOME/.ernest-cc}"

if [ -z "$SEED" ] || [ ! -d "$SEED" ]; then
  echo "usage: scripts/seed-profile.sh <seed-dir>" >&2
  echo "  seed-dir must contain identity.env (NAME/ROLE/COMPANY/ICP/REDLINES)" >&2
  exit 2
fi
if [ ! -f "$SEED/identity.env" ]; then
  echo "seed: $SEED/identity.env is missing." >&2
  exit 2
fi
if [ ! -x "$PROFILE_DIR/bin/ernest" ]; then
  echo "seed: no installed profile at $PROFILE_DIR. Run ./install.sh first." >&2
  exit 10
fi

set -a; . "$SEED/identity.env"; set +a
: "${NAME:?identity.env must set NAME}"
: "${COMPANY:?identity.env must set COMPANY}"

echo "Seeding $PROFILE_DIR for $NAME @ $COMPANY"

"$PROFILE_DIR/bin/ernest" onboard --non-interactive \
  --name "$NAME" --role "${ROLE:-CEO}" --company "$COMPANY" \
  --icp "${ICP:-}" --redlines "${REDLINES:-}"

# Memory files are installed verbatim — they are prose the model reads, not
# something onboarding can synthesize from five flags.
if [ -d "$SEED/memory" ]; then
  for f in "$SEED/memory"/*.md; do
    [ -e "$f" ] || continue
    cp "$f" "$PROFILE_DIR/memory/$(basename "$f")"
    echo "  memory/$(basename "$f")"
  done
fi

# Rubrics live under data/, which refresh never touches.
if [ -d "$SEED/data/grading" ]; then
  mkdir -p "$PROFILE_DIR/data/grading"
  for f in "$SEED/data/grading"/*.json; do
    [ -e "$f" ] || continue
    python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$f" || {
      echo "  SKIPPED $(basename "$f") — does not parse" >&2; continue; }
    cp "$f" "$PROFILE_DIR/data/grading/$(basename "$f")"
    echo "  data/grading/$(basename "$f")"
  done
fi

echo
echo "Verifying..."
"$PROFILE_DIR/bin/ernest" doctor | tail -20
echo
echo "Done. The SAMPLE-data warning should be gone from \`ernest start\`."
