#!/usr/bin/env bash
# Deploy the Ernest brain (shared memory + watch-cards + drafts API) to the VPS so
# the +VPS surface combos work: Telegram/Slack 24/7 AND local Claude Code / Cowork
# all share ONE state. Run from the ernest-cc repo root, with the CEO's go-ahead.
#
#   ./adapters/vps/deploy-brain.sh            # interactive confirm
#   ./adapters/vps/deploy-brain.sh --yes      # skip the prompt (still pre-backs-up)
#
# Security posture (deliberate):
#   * The brain binds 127.0.0.1 on the VPS — never exposed to the open internet.
#     The laptop reaches it over an SSH tunnel (printed at the end). The server
#     ALSO fails closed: the systemd unit sets ERNEST_REQUIRE_TOKEN=1, so it
#     refuses to start without a bearer even on loopback.
#   * Secrets never hit a command line (no `ps` argv leak): the VPS password goes
#     to sshpass via the SSHPASS env (`-e`), and the brain bearer is shipped inside
#     an scp'd 0600 env file — never passed as an ssh/bash argument.
#   * App/connector tokens live ONLY in the VPS env file (0600). The laptop holds
#     just the bearer, in ~/ernest.brain-token.txt (0600), never printed/committed.
#
# Requires: ~/ernest.secrets.env with VPS_IP and VPS_PASSWORD; `sshpass`, `ssh`,
# `scp`, `tar` locally. Stdlib-only on the VPS (system python3 ≥ 3.9; no pip).
# NOTE: the first connection uses accept-new TOFU over a password login; for a
# hardened bootstrap, pin the host key out-of-band or switch to SSH key auth.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SECRETS="${ERNEST_SECRETS_FILE:-$HOME/ernest.secrets.env}"
REMOTE_DIR="/opt/ernest-brain"
SERVICE="ernest-brain"
PORT="${ERNEST_BRAIN_PORT:-8787}"
TOKEN_FILE="$HOME/ernest.brain-token.txt"
ASSUME_YES=0
[[ "${1:-}" == "--yes" || "${1:-}" == "-y" ]] && ASSUME_YES=1

die() { echo "ERROR: $*" >&2; exit 1; }

# --- preflight ---------------------------------------------------------------
[[ -f "$SECRETS" ]] || die "secrets file not found: $SECRETS (need VPS_IP, VPS_PASSWORD)"
command -v sshpass >/dev/null || die "sshpass not installed (brew install hudochenkov/sshpass/sshpass)"
command -v ssh >/dev/null || die "ssh not found"
# shellcheck disable=SC1090
set -a; source "$SECRETS"; set +a
: "${VPS_IP:?VPS_IP missing in secrets}"
: "${VPS_PASSWORD:?VPS_PASSWORD missing in secrets}"
VPS_USER="${VPS_USER:-root}"

# Reuse an existing bearer if present, else generate one (created 0600 from the
# start via umask, never printed).
if [[ -f "$TOKEN_FILE" ]]; then
  ERNEST_BRAIN_TOKEN="$(tr -d '\n' < "$TOKEN_FILE")"
else
  ERNEST_BRAIN_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  ( umask 077; printf '%s' "$ERNEST_BRAIN_TOKEN" > "$TOKEN_FILE" )
fi
[[ -n "$ERNEST_BRAIN_TOKEN" ]] || die "empty bearer token"

# Password to sshpass via env (NOT argv). ssh/scp via wrapper funcs.
export SSHPASS="$VPS_PASSWORD"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 -o ServerAliveInterval=15)
rsh() { sshpass -e ssh "${SSH_OPTS[@]}" "$VPS_USER@$VPS_IP" "$@"; }
rcp() { sshpass -e scp "${SSH_OPTS[@]}" "$@"; }

echo "About to deploy the Ernest brain:"
echo "  target : $VPS_USER@$VPS_IP  ->  $REMOTE_DIR  (systemd: $SERVICE, 127.0.0.1:$PORT)"
echo "  bearer : stored at $TOKEN_FILE (not shown)"
echo "  backup : existing $REMOTE_DIR is tarred to a pruned ${REMOTE_DIR}.bak-* first (token excluded)"
if [[ "$ASSUME_YES" -ne 1 ]]; then
  read -r -p "Proceed? [y/N] " ans; [[ "$ans" =~ ^[Yy]$ ]] || die "aborted"
fi

# --- connectivity + port pre-check -------------------------------------------
rsh "true" || die "cannot reach $VPS_USER@$VPS_IP over ssh (check VPS_IP/VPS_PASSWORD)"
rsh "mkdir -p '$REMOTE_DIR'"
# Best-effort: refuse if the port is already taken (e.g. by hermes). ss may be
# absent on minimal hosts — then we skip the check rather than block.
if rsh "ss -ltn 2>/dev/null | grep -q ':$PORT '"; then
  die "port $PORT is already in use on the VPS. Set ERNEST_BRAIN_PORT to a free port and retry."
fi

# --- bundle (engine + brain + sanitized memory seed; stdlib, no secrets) ------
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/ernest-brain.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/pkg"
cp -R "$ROOT/ernest" "$STAGE/pkg/ernest"
cp -R "$ROOT/brain"  "$STAGE/pkg/brain"
cp -R "$ROOT/memory" "$STAGE/pkg/memory"
find "$STAGE/pkg" -name '__pycache__' -type d -prune -exec rm -rf {} +
( cd "$STAGE/pkg" && tar czf "$STAGE/bundle.tgz" . )

# Brain env file built locally at 0600; the token travels by scp (encrypted),
# never as an ssh/bash argument.
( umask 077; cat > "$STAGE/brain.env" <<ENVEOF
ERNEST_BRAIN_TOKEN=$ERNEST_BRAIN_TOKEN
ERNEST_PROFILE_DIR=$REMOTE_DIR/state
ERNEST_MODE=vps
ERNEST_REQUIRE_TOKEN=1
ENVEOF
)

echo "==> uploading bundle + env"
rcp "$STAGE/bundle.tgz" "$VPS_USER@$VPS_IP:$REMOTE_DIR/bundle.tgz"
rcp "$STAGE/brain.env"  "$VPS_USER@$VPS_IP:$REMOTE_DIR/brain.env"

echo "==> installing on VPS (backup, systemd unit, loopback bind, health-check)"
# All logic below runs REMOTELY: single-quoted heredoc => no local expansion.
# The three safe values (dir, service, port) arrive as positional args.
rsh "bash -s -- '$REMOTE_DIR' '$SERVICE' '$PORT'" <<'REMOTE'
set -e
RD="$1"; SVC="$2"; PORT="$3"
cd "$RD"

# Backup existing install (exclude the new uploads + the token); keep newest 3.
if [ -n "$(ls -A "$RD" 2>/dev/null | grep -v -e '^bundle.tgz$' -e '^brain.env$' || true)" ]; then
  ( umask 077; tar czf "${RD}.bak-$(date +%s).tgz" -C "$RD" \
      --exclude=./bundle.tgz --exclude=./brain.env . )
  ls -t "${RD}".bak-*.tgz 2>/dev/null | tail -n +4 | xargs -r rm -f
fi

tar xzf bundle.tgz && rm -f bundle.tgz
chmod 600 "$RD/brain.env"
mkdir -p "$RD/state"
# Seed canonical memory ONCE; never clobber live state on redeploy.
[ -d "$RD/state/memory" ] || cp -R "$RD/memory" "$RD/state/memory"

PY="$(command -v python3)"
[ -n "$PY" ] || { echo "python3 not found on the VPS"; exit 1; }

cat > "/etc/systemd/system/$SVC.service" <<UNIT
[Unit]
Description=Ernest brain (shared memory/cards/drafts MCP, draft-first)
After=network.target

[Service]
Type=simple
WorkingDirectory=$RD
EnvironmentFile=$RD/brain.env
ExecStart=$PY -m brain.server --host 127.0.0.1 --port $PORT
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$RD

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now "$SVC.service"
sleep 1
if ! systemctl is-active --quiet "$SVC.service"; then
  echo "service failed to start; recent logs:"
  journalctl -u "$SVC.service" -n 20 --no-pager 2>/dev/null || true
  exit 1
fi

# Liveness: prefer curl, then wget, then python3 (guaranteed — it's the runtime).
if command -v curl >/dev/null 2>&1; then
  curl -fsS "http://127.0.0.1:$PORT/health" && echo
elif command -v wget >/dev/null 2>&1; then
  wget -qO- "http://127.0.0.1:$PORT/health" && echo
else
  "$PY" - "$PORT" <<'PYEOF'
import sys, urllib.request
with urllib.request.urlopen("http://127.0.0.1:%s/health" % sys.argv[1], timeout=5) as r:
    sys.exit(0 if r.status == 200 else 1)
PYEOF
  echo "health ok (python probe)"
fi
REMOTE

cat <<EOF

✓ Brain deployed and healthy on the VPS (127.0.0.1:$PORT, systemd: $SERVICE).

Connect a LAPTOP surface (Claude Code / Cowork) to it:

  1) Open an SSH tunnel (keep it running, or add to ~/.ssh/config / autossh):
       ssh -N -L $PORT:127.0.0.1:$PORT $VPS_USER@$VPS_IP
  2) Export the bearer (from $TOKEN_FILE) in your shell:
       export ERNEST_BRAIN_TOKEN="\$(cat $TOKEN_FILE)"
  3) In Claude, run:  /ernest-connect-brain --url http://127.0.0.1:$PORT

Now local + Telegram/Slack share one memory, one set of reminder cards, one draft
store. Manage: systemctl status|restart $SERVICE  ·  logs: journalctl -u $SERVICE -f
EOF
