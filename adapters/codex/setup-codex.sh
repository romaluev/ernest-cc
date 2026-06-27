#!/usr/bin/env bash
# Ernest — Codex adapter setup. Makes Ernest usable from OpenAI Codex CLI, reusing
# the same engine + memory as the Claude Code build. Idempotent and additive: it
# only adds an `ernest` Codex profile, named MCP servers, prompts, and AGENTS.md —
# it never rewrites your existing Codex config. Honors $CODEX_HOME for safe testing.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"      # ernest-cc repo root
PROFILE_DIR="${ERNEST_PROFILE_DIR:-$HOME/.ernest-cc}"
CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"
PROMPTS_DIR="$CODEX_DIR/prompts"
CONFIG="$CODEX_DIR/config.toml"

command -v codex >/dev/null 2>&1 || { echo "Codex CLI not found. Install it first (npm i -g @openai/codex), then re-run." >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "Ernest needs python3." >&2; exit 1; }

# 1. Ensure the Ernest engine + memory exist (reuse the local install).
if [ ! -x "$PROFILE_DIR/bin/ernest" ]; then
  echo "→ Installing the Ernest engine (local mode)…"
  ERNEST_PROFILE_DIR="$PROFILE_DIR" "$ROOT/install.sh" --no-run >/dev/null
fi
ERNEST_BIN="$PROFILE_DIR/bin/ernest"

# 2. Persona: AGENTS.md in the Ernest working dir (Codex reads it from cwd upward).
cp "$ROOT/adapters/codex/AGENTS.md" "$PROFILE_DIR/AGENTS.md"

# 3. Slash-command prompts (invoked as /ernest-… inside Codex).
mkdir -p "$PROMPTS_DIR"
_prompt() { printf '%s\n' "$2" > "$PROMPTS_DIR/$1.md"; }
_prompt ernest-brief   "Run \`$ERNEST_BIN start\` and give me the morning brief: Bottom line, then up to 6 things that need me (who · action · why now · source). Remind-only; draft nothing."
_prompt ernest-watch   "Run \`$ERNEST_BIN watch\`. Surface only what slipped, as reminder cards with sources. Never draft or send."
_prompt ernest-grade   "Run \`$ERNEST_BIN grade\` (add --talent for candidates). Cast a wide net, then rank by match score; Tier-1 first. Remind/assign only."
_prompt ernest-draft   "Prepare draft replies for the concern I name (e.g. important-followups) via \`$ERNEST_BIN draft --concern <id>\`. In my voice, short, clear next step. Show me for approval — send NOTHING."
_prompt ernest-doctor  "Run \`$ERNEST_BIN doctor\`. Diagnose what's missing or off and propose safe fixes; ask before anything needing my login or credentials."
_prompt ernest-setup   "Walk me through setup in plain words (name, company, who's a good lead, red lines, which tools to watch), then run \`$ERNEST_BIN onboard\` with my answers. Local-first; never overwrite what's set."

# 4. MCP servers — local memory always; the brain only if a URL is configured.
codex mcp add ernest-local-memory -- npx -y @modelcontextprotocol/server-memory >/dev/null 2>&1 || true
if [ -n "${ERNEST_BRAIN_URL:-}" ]; then
  ERNEST_BRAIN_TOKEN="${ERNEST_BRAIN_TOKEN:-}" \
    codex mcp add ernest-brain --url "$ERNEST_BRAIN_URL" --bearer-token-env-var ERNEST_BRAIN_TOKEN >/dev/null 2>&1 || true
  echo "→ Registered brain MCP (draft-first; tokens stay server-side)."
else
  echo "→ Local-memory MCP registered. (No brain URL set — running local-first.)"
fi

# 5. A safe `ernest` Codex profile: writes only in the workspace, asks before risk.
#    Appended once; never duplicated.
touch "$CONFIG"
if ! grep -q '^\[profiles.ernest\]' "$CONFIG"; then
  cat >> "$CONFIG" <<'EOF'

# --- Ernest adapter (added by setup-codex.sh) ---
[profiles.ernest]
approval_policy = "on-request"   # ask before anything risky
sandbox_mode = "workspace-write" # can write the vault/memory in cwd; no network, no outside writes
EOF
  echo "→ Added [profiles.ernest] (workspace-write + on-request approval)."
else
  echo "→ [profiles.ernest] already present (left as-is)."
fi

cat <<EOF

Ernest is ready on Codex.

Use it (run from the Ernest folder so AGENTS.md + the engine are picked up):

  cd "$PROFILE_DIR"
  codex --profile ernest

Then talk to it, or use a slash command: /ernest-brief, /ernest-grade, /ernest-draft, /ernest-doctor, /ernest-setup

Safety on Codex: draft-first by these rules + Codex's approval/sandbox + draft-first MCP only.
Do NOT add raw send-capable connectors to this profile — use the Claude Code build (deterministic
gate) or the Telegram bot for live sends. See docs/codex.md.
EOF
