#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE_DIR="${ERNEST_PROFILE_DIR:-$HOME/.ernest-cc}"
VAULT_DIR="${ERNEST_LOCAL_VAULT:-$HOME/ErnestVault}"
MEMORY_FILE="${ERNEST_LOCAL_MEMORY_FILE:-$VAULT_DIR/memory.json}"
MODE="${ERNEST_MODE:-local}"

usage() {
  printf '%s\n' "Usage: ./install.sh [--health-only] [--refresh] [--no-run] [--mode local|vps]"
  printf '%s\n' "  --refresh  update code/skills/engine in an existing profile; keep memory + config"
  printf '%s\n' "  --no-run   do not run the first brief after installing"
}

HEALTH_ONLY=0
REFRESH=0
NO_RUN=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --health-only) HEALTH_ONLY=1 ;;
    --refresh) REFRESH=1 ;;
    --no-run) NO_RUN=1 ;;
    --mode) shift; MODE="${1:-local}" ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; usage; exit 2 ;;
  esac
  shift
done

# Best-effort: put a short `ernest` command on PATH so the CEO never types a
# long path. Returns the command name to show in instructions.
link_to_path() {
  local target="$PROFILE_DIR/bin/ernest" dir
  # Only link the canonical install; never point a global command at a custom
  # or sandbox profile.
  if [ "$PROFILE_DIR" != "$HOME/.ernest-cc" ]; then
    printf '%s' "$target"
    return 0
  fi
  for dir in "$HOME/.local/bin" /usr/local/bin /opt/homebrew/bin; do
    case ":$PATH:" in *":$dir:"*) ;; *) continue ;; esac
    if mkdir -p "$dir" 2>/dev/null && ln -sf "$target" "$dir/ernest" 2>/dev/null; then
      printf 'ernest'
      return 0
    fi
  done
  printf '%s' "$target"
}

# Crash-safe file copy: stage to a temp path on the same filesystem, then rename
# over the destination (atomic). A crash mid-copy never leaves a half-written file.
_swap_file() {
  local rel="$1" stage
  stage="$PROFILE_DIR/.stage-$(printf '%s' "$rel" | tr '/.' '__').$$"
  cp "$ROOT/$rel" "$stage"
  mv -f "$stage" "$PROFILE_DIR/$rel"
}

# Crash-safe directory replace: stage a full copy, swap the old aside, move the
# new in, then delete the old. The only window is two renames, not an rm -rf gap.
# NOTE: only ever touches CORE dirs — never memory/, data/, env, or .mcp.json.
_swap_dir() {
  local name="$1" stage old
  stage="$PROFILE_DIR/.stage-$name.$$"
  old="$PROFILE_DIR/.old-$name.$$"
  rm -rf "$stage" "$old"
  cp -R "$ROOT/$name" "$stage"
  [ -e "$PROFILE_DIR/$name" ] && mv "$PROFILE_DIR/$name" "$old"
  mv "$stage" "$PROFILE_DIR/$name"
  rm -rf "$old"
}

# --- three-layer composition (core + custom overlay) -------------------------
# Top-level skills/commands/agents are a COMPOSED VIEW of:
#   core   = whatever ships in this repo ($ROOT)         [replaced on every refresh]
#   custom = the CEO's own items under $PROFILE_DIR/custom [NEVER touched by refresh]
# custom wins on a name clash, so the CEO can override a shipped skill without
# editing core. memory/, data/, logs/, env, .mcp.json, custom/ are never replaced.
OVERLAY_DIRS="skills commands agents"

ensure_custom() {
  local d
  for d in $OVERLAY_DIRS; do mkdir -p "$PROFILE_DIR/custom/$d"; done
  [ -f "$PROFILE_DIR/custom/README.md" ] || cat > "$PROFILE_DIR/custom/README.md" <<'EOF'
# Ernest custom layer (yours — never overwritten by updates)

Put your own skills/commands/agents here and they survive every update:
  custom/skills/<your-skill>/SKILL.md
  custom/commands/<your-command>.md
  custom/agents/<your-agent>.md

A custom item with the SAME name as a shipped one OVERRIDES it (custom wins).
To tweak a shipped skill, copy it from skills/ into custom/skills/ and edit the copy.
Config/permission overrides go in .claude/settings.local.json (merged by Claude Code).
EOF
}

# Rescue any top-level item that is neither core-owned nor already in custom into
# custom/ — so a skill the CEO dropped straight into skills/ is preserved forever.
rescue_user_items() {
  local name="$1" item base dest="$PROFILE_DIR/custom/$1"
  [ -d "$PROFILE_DIR/$name" ] || return 0
  mkdir -p "$dest"
  for item in "$PROFILE_DIR/$name"/*; do
    [ -e "$item" ] || continue
    base="$(basename "$item")"
    if [ ! -e "$ROOT/$name/$base" ] && [ ! -e "$dest/$base" ]; then
      mv "$item" "$dest/$base"
      printf '  rescued user %s/%s into custom/ (preserved across updates)\n' "$name" "$base"
    fi
  done
}

# Rebuild a top-level overlay dir = core items, then custom items (custom wins).
# Crash-safe: build a staging dir, swap old aside, move new in, drop old.
compose_overlay() {
  local name="$1" stage old item base
  stage="$PROFILE_DIR/.stage-$name.$$"
  old="$PROFILE_DIR/.old-$name.$$"
  rm -rf "$stage" "$old"
  mkdir -p "$stage"
  if [ -d "$ROOT/$name" ]; then
    for item in "$ROOT/$name"/*; do [ -e "$item" ] && cp -R "$item" "$stage/"; done
  fi
  if [ -d "$PROFILE_DIR/custom/$name" ]; then
    for item in "$PROFILE_DIR/custom/$name"/*; do
      [ -e "$item" ] || continue
      base="$(basename "$item")"
      rm -rf "$stage/$base"
      cp -R "$item" "$stage/$base"
    done
  fi
  [ -e "$PROFILE_DIR/$name" ] && mv "$PROFILE_DIR/$name" "$old"
  mv "$stage" "$PROFILE_DIR/$name"
  rm -rf "$old"
}

copy_code() {
  # Pure-core code/config: replaced wholesale (atomic). No user content lives here.
  _swap_file CLAUDE.md
  _swap_file settings.json
  _swap_file ernest.yaml
  _swap_dir hooks
  _swap_dir ernest
  # Output styles make Claude answer in one consistent house format every turn.
  _swap_dir .claude
  # Overlay dirs: compose core + custom so CEO additions/overrides always survive.
  ensure_custom
  local d
  for d in $OVERLAY_DIRS; do
    rescue_user_items "$d"
    compose_overlay "$d"
  done
}

write_launcher() {
  mkdir -p "$PROFILE_DIR/bin"
  cat > "$PROFILE_DIR/bin/ernest" <<EOF
#!/usr/bin/env bash
# Ernest CLI launcher (generated by install.sh). Runs the local-first engine
# against this profile, with no network dependency.
export ERNEST_PROFILE_DIR="$PROFILE_DIR"
[ -f "$PROFILE_DIR/env" ] && set -a && . "$PROFILE_DIR/env" && set +a
export PYTHONPATH="$PROFILE_DIR\${PYTHONPATH:+:\$PYTHONPATH}"
exec python3 -m ernest.cli "\$@"
EOF
  chmod +x "$PROFILE_DIR/bin/ernest"
}

require_file() {
  local path="$1"
  if [ ! -f "$ROOT/$path" ]; then
    printf 'Missing required file: %s\n' "$path" >&2
    exit 1
  fi
}

health_check() {
  require_file "CLAUDE.md"
  require_file ".claude-plugin/plugin.json"
  require_file "settings.json"
  require_file ".mcp.json"
  require_file "ernest.yaml"
  require_file "hooks/pre_tool_use.py"
  require_file "hooks/capture_learnings.py"
  require_file "ernest/cli.py"
  require_file "ernest/gate.py"
  require_file "ernest/render.py"
  require_file "ernest/preferences.py"
  require_file "ernest/feedback.py"
  require_file "memory/preferences.md"
  require_file "skills/ernest-preferences/SKILL.md"
  require_file ".claude/output-styles/ernest.md"
  require_file "docs/examples.md"
  require_file "docs/connectors.md"
  require_file "docs/quickstart.md"
  require_file "skills/morning-brief/SKILL.md"
  require_file "skills/account-followup-recovery/SKILL.md"
  require_file "skills/inbox-prospect-followup/SKILL.md"
  require_file "skills/call-prep/SKILL.md"
  require_file "skills/call-coaching/SKILL.md"
  require_file "skills/support-triage/SKILL.md"
  require_file "skills/hiring-pipeline/SKILL.md"
  require_file "skills/lead-enrichment/SKILL.md"
  require_file "skills/deal-desk/SKILL.md"
  require_file "commands/ernest-brief.md"
  require_file "scripts/self-update.sh"
  require_file ".claude-plugin/plugin.json"
  require_file ".claude-plugin/marketplace.json"
  require_file "hooks/hooks.json"
  require_file "hooks/session_context.py"
  require_file ".claude/settings.json"
  printf 'Ernest health check: ok\n'
}

check_prereqs() {
  if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' "Ernest needs python3, which isn't installed." >&2
    printf '%s\n' "Install it (macOS: 'xcode-select --install' or python.org), then re-run." >&2
    exit 1
  fi
  # npx/node only powers the optional local-memory MCP; warn, don't fail.
  if [ "$MODE" = "local" ] && ! command -v npx >/dev/null 2>&1; then
    printf '%s\n' "Note: 'npx' (Node) not found — the optional local memory server is skipped. Everything else works." >&2
  fi
}

check_prereqs
health_check

if [ "$HEALTH_ONLY" = "1" ]; then
  exit 0
fi

if [ "$REFRESH" = "1" ]; then
  if [ ! -d "$PROFILE_DIR" ]; then
    printf 'Nothing to refresh: %s does not exist. Run ./install.sh first.\n' "$PROFILE_DIR" >&2
    exit 1
  fi
  copy_code
  write_launcher
  printf 'Refreshed code/skills/engine in %s (memory and config preserved).\n' "$PROFILE_DIR"
  exit 0
fi

mkdir -p "$PROFILE_DIR" "$PROFILE_DIR/bin" "$VAULT_DIR/Ernest/00-Watch" "$VAULT_DIR/Ernest/00-Daily" "$VAULT_DIR/Ernest/00-Drafts" "$VAULT_DIR/Ernest/Hygiene/snapshots"
if [ ! -f "$MEMORY_FILE" ]; then
  printf '{}\n' > "$MEMORY_FILE"
fi

copy_code
# Seed memory/data ONLY on a first install — never clobber the CEO's memory or
# data exports if they re-run plain ./install.sh. (--refresh never touches these.)
[ -d "$PROFILE_DIR/memory" ] || cp -R "$ROOT"/memory "$PROFILE_DIR"/
[ -d "$PROFILE_DIR/data" ] || cp -R "$ROOT"/data "$PROFILE_DIR"/
write_launcher

if [ "$MODE" = "vps" ]; then
  if [ -z "${ERNEST_BRAIN_URL:-}" ] || [ -z "${ERNEST_BRAIN_TOKEN:-}" ]; then
    printf '%s\n' "VPS mode selected."
    printf '%s\n' "Set ERNEST_BRAIN_URL and ERNEST_BRAIN_TOKEN, then rerun:"
    printf '%s\n' "  ERNEST_BRAIN_URL=https://... ERNEST_BRAIN_TOKEN=... ./install.sh"
    exit 1
  fi
  cat > "$PROFILE_DIR/.mcp.json" <<EOF
{
  "mcpServers": {
    "ernest-brain": {
      "type": "http",
      "url": "$ERNEST_BRAIN_URL",
      "headers": {
        "Authorization": "Bearer $ERNEST_BRAIN_TOKEN"
      }
    }
  }
}
EOF
else
  MODE="local"
  cat > "$PROFILE_DIR/.mcp.json" <<EOF
{
  "mcpServers": {
    "local-memory": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-memory"
      ],
      "env": {
        "MEMORY_FILE_PATH": "$MEMORY_FILE"
      }
    }
  }
}
EOF
fi

cat > "$PROFILE_DIR/env" <<EOF
ERNEST_MODE=$MODE
ERNEST_PROFILE_DIR=$PROFILE_DIR
ERNEST_LOCAL_VAULT=$VAULT_DIR
ERNEST_LOCAL_MEMORY_FILE=$MEMORY_FILE
ERNEST_SRC_DIR=$ROOT
ERNEST_UPDATE_CHANNEL=${ERNEST_UPDATE_CHANNEL:-stable}
ERNEST_BRAIN_URL=${ERNEST_BRAIN_URL:-}
ERNEST_BRAIN_TOKEN=${ERNEST_BRAIN_TOKEN:-}
EOF

# Lock down anything that can hold a bearer token / secret to owner-only.
chmod 600 "$PROFILE_DIR/env" "$PROFILE_DIR/.mcp.json" 2>/dev/null || true

cat > "$PROFILE_DIR/launchd.example.plist" < "$ROOT/cron/com.notiky.ernest.example.plist"
cat > "$PROFILE_DIR/crontab.example" < "$ROOT/cron/crontab.example"

ERNEST_CMD="$(link_to_path)"

if [ "$NO_RUN" != "1" ]; then
  printf '\n%s\n' "Here is what needs you right now:"
  printf '%s\n' "------------------------------------------------------------"
  "$PROFILE_DIR/bin/ernest" start || true
  printf '%s\n' "------------------------------------------------------------"
fi

printf '\n%s\n' "Ernest is installed ($MODE mode)."
printf '%s\n' ""
printf '%s\n' "From now on, just run:"
printf '%s\n' "    $ERNEST_CMD start"
printf '%s\n' ""
printf '%s\n' "Optional, when you have a minute:"
printf '%s\n' "  - $ERNEST_CMD onboard          tell Ernest about you and your company"
printf '%s\n' "  - docs/examples.md              copy-paste prompts (simple + complex)"
printf '%s\n' "  - open Claude Code in $PROFILE_DIR and run /ernest-onboard to connect Gmail/HubSpot/Slack"
