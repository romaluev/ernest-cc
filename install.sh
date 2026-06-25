#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE_DIR="${ERNEST_PROFILE_DIR:-$HOME/.ernest-cc}"
VAULT_DIR="${ERNEST_LOCAL_VAULT:-$HOME/ErnestVault}"
MEMORY_FILE="${ERNEST_LOCAL_MEMORY_FILE:-$VAULT_DIR/memory.json}"
MODE="${ERNEST_MODE:-local}"

usage() {
  printf '%s\n' "Usage: ./install.sh [--health-only] [--mode local|vps]"
}

HEALTH_ONLY=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --health-only) HEALTH_ONLY=1 ;;
    --mode) shift; MODE="${1:-local}" ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; usage; exit 2 ;;
  esac
  shift
done

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
  require_file "skills/morning-brief/SKILL.md"
  require_file "skills/account-followup-recovery/SKILL.md"
  require_file "skills/inbox-prospect-followup/SKILL.md"
  require_file "commands/ernest-brief.md"
  printf 'Ernest health check: ok\n'
}

health_check

if [ "$HEALTH_ONLY" = "1" ]; then
  exit 0
fi

mkdir -p "$PROFILE_DIR" "$VAULT_DIR/Ernest/00-Watch" "$VAULT_DIR/Ernest/00-Daily" "$VAULT_DIR/Ernest/Hygiene/snapshots"
if [ ! -f "$MEMORY_FILE" ]; then
  printf '{}\n' > "$MEMORY_FILE"
fi

cp -R "$ROOT"/CLAUDE.md "$ROOT"/settings.json "$ROOT"/ernest.yaml "$PROFILE_DIR"/
cp -R "$ROOT"/skills "$ROOT"/commands "$ROOT"/agents "$ROOT"/hooks "$ROOT"/memory "$ROOT"/data "$PROFILE_DIR"/

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
ERNEST_BRAIN_URL=${ERNEST_BRAIN_URL:-}
ERNEST_BRAIN_TOKEN=${ERNEST_BRAIN_TOKEN:-}
EOF

cat > "$PROFILE_DIR/launchd.example.plist" < "$ROOT/cron/com.notiky.ernest.example.plist"
cat > "$PROFILE_DIR/crontab.example" < "$ROOT/cron/crontab.example"

printf '%s\n' ""
printf '%s\n' "Ernest installed to $PROFILE_DIR"
printf '%s\n' "Mode: $MODE"
printf '%s\n' "Vault: $VAULT_DIR"
printf '%s\n' ""
printf '%s\n' "Next:"
printf '%s\n' "1. Sign in to Claude Code / Claude Desktop if needed."
printf '%s\n' "2. Authorize Gmail/HubSpot/Slack/Calendar through the VPS brain or local connector flow."
printf '%s\n' "3. Start Claude Code in $PROFILE_DIR and run /ernest-onboard."
