#!/usr/bin/env bash
# Ernest safe self-update — daily-from-GitHub with validate-then-rollback.
#
# Subcommands:
#   check   (cron, daily)  fetch + ff-guard + validate the new commit in a throwaway
#                          worktree; if good, stage a pending marker + one-tap card.
#                          Does NOT touch the live install.
#   apply   (CEO one-tap)  re-validate the new commit, ff-merge, install.sh --refresh
#                          (atomic; preserves memory/custom/state), post-verify,
#                          AUTO-ROLLBACK to the previous commit on any failure.
#   auto    (canary)       check then apply in one go (for a non-CEO soak surface).
#   status                 print current HEAD, channel, and pending/rollback state.
#
# Safety invariants:
#   - ff-only: a force-pushed/diverged branch is refused, never reset --hard.
#   - a commit that fails the gate self-test is never applied (supply-chain backstop).
#   - install.sh --refresh only rewrites CORE; memory/custom/state are untouched.
#   - after a rollback the next run is skipped until a human clears the flag
#     (no daily rollback-loop).
set -euo pipefail

SRC_DIR="${ERNEST_SRC_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PROFILE_DIR="${ERNEST_PROFILE_DIR:-$HOME/.ernest-cc}"
CHANNEL="${ERNEST_UPDATE_CHANNEL:-stable}"
LOG="$PROFILE_DIR/logs/selfupdate.log"
LOCK="$PROFILE_DIR/logs/selfupdate.lock"
PENDING="$PROFILE_DIR/logs/update-pending.json"
ROLLBACK_FLAG="$PROFILE_DIR/logs/update-rolledback.flag"
CARD_DIR="${ERNEST_LOCAL_VAULT:-$HOME/ErnestVault}/Ernest/00-Watch"

log() { mkdir -p "$(dirname "$LOG")"; printf '%s|%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG"; }

card() {
  mkdir -p "$CARD_DIR" 2>/dev/null || return 0
  local f="$CARD_DIR/update-$(date -u +%Y%m%d-%H%M%S).md"
  printf '# Ernest update\n\n%s\n\nReply draft these when you want me to prepare actions.\n' "$*" > "$f" 2>/dev/null || true
}

acquire_lock() {
  mkdir -p "$(dirname "$LOCK")"
  if ! mkdir "$LOCK" 2>/dev/null; then
    log "another self-update is running; exiting"
    exit 0
  fi
  trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT
}

short() { git -C "$SRC_DIR" rev-parse --short "$1" 2>/dev/null || echo "$1"; }

# Validate a tree (worktree or profile source): health gauntlet + gate self-test.
validate_tree() {
  local d="$1"
  bash "$d/install.sh" --health-only >/dev/null 2>&1 || return 1
  ( cd "$d" && PYTHONPATH="$d" python3 -m ernest.gate --selftest >/dev/null 2>&1 ) || return 1
  return 0
}

# Post-promote verification, run against the SOURCE checkout now on the new commit.
post_verify() {
  if [ "${ERNEST_UPDATE_FORCE_POSTFAIL:-0}" = "1" ]; then
    return 1   # test hook: exercise the rollback path deterministically
  fi
  validate_tree "$SRC_DIR"
}

ensure_git() {
  command -v git >/dev/null 2>&1 || { log "git not available"; return 1; }
  git -C "$SRC_DIR" rev-parse --git-dir >/dev/null 2>&1 || { log "SRC_DIR is not a git repo: $SRC_DIR"; return 1; }
}

fetch_target() {  # echoes target SHA, returns non-zero on fetch failure
  git -C "$SRC_DIR" fetch --quiet origin "$CHANNEL" 2>/dev/null || return 1
  git -C "$SRC_DIR" rev-parse "origin/$CHANNEL" 2>/dev/null || return 1
}

is_ff() {  # HEAD must be an ancestor of origin/CHANNEL
  git -C "$SRC_DIR" merge-base --is-ancestor HEAD "origin/$CHANNEL" 2>/dev/null
}

cmd_check() {
  ensure_git || return 1
  local OLD NEW WT
  OLD="$(git -C "$SRC_DIR" rev-parse HEAD)"
  NEW="$(fetch_target)" || { log "fetch failed"; return 1; }
  if [ "$OLD" = "$NEW" ]; then log "up-to-date ($(short HEAD))"; rm -f "$PENDING"; return 0; fi
  if ! is_ff; then
    log "NON-FF divergence: HEAD=$OLD origin/$CHANNEL=$NEW — refusing"
    card "Update needs review: the $CHANNEL branch diverged (non-fast-forward). Nothing changed."
    return 2
  fi
  WT="$(mktemp -d "${TMPDIR:-/tmp}/ernest-wt.XXXXXX")"
  if ! git -C "$SRC_DIR" worktree add --quiet --detach "$WT" "$NEW" 2>/dev/null; then
    log "worktree add failed"; rm -rf "$WT"; return 1
  fi
  if validate_tree "$WT"; then
    git -C "$SRC_DIR" worktree remove --force "$WT" 2>/dev/null || true; rm -rf "$WT"
    printf '{"old":"%s","new":"%s","channel":"%s","validated":true}\n' "$OLD" "$NEW" "$CHANNEL" > "$PENDING"
    log "validated $(short "$NEW"); staged pending"
    card "Update ready ($(short "$NEW") on $CHANNEL) — validated. Reply 'apply update' to install. Auto-rollback if anything fails."
    return 0
  fi
  git -C "$SRC_DIR" worktree remove --force "$WT" 2>/dev/null || true; rm -rf "$WT"
  rm -f "$PENDING"
  log "VALIDATION FAILED for $(short "$NEW") — not staged"
  card "Update $(short "$NEW") failed validation (gate self-test or health check). NOT applied."
  return 3
}

cmd_apply() {
  ensure_git || return 1
  if [ -f "$ROLLBACK_FLAG" ]; then
    log "skip apply: previous update rolled back; clear $ROLLBACK_FLAG to retry"
    card "Skipping update: the last attempt was rolled back. Needs a look before retrying."
    return 4
  fi
  local OLD NEW SNAP
  OLD="$(git -C "$SRC_DIR" rev-parse HEAD)"
  NEW="$(fetch_target)" || { log "fetch failed"; return 1; }
  if [ "$OLD" = "$NEW" ]; then log "apply: already current"; rm -f "$PENDING"; return 0; fi
  if ! is_ff; then log "apply abort: non-ff"; card "Update aborted (non-fast-forward)."; return 2; fi

  # Pre-validate the target so a bad commit is never merged in the first place.
  local WT; WT="$(mktemp -d "${TMPDIR:-/tmp}/ernest-wt.XXXXXX")"
  git -C "$SRC_DIR" worktree add --quiet --detach "$WT" "$NEW" 2>/dev/null || { log "worktree add failed"; rm -rf "$WT"; return 1; }
  if ! validate_tree "$WT"; then
    git -C "$SRC_DIR" worktree remove --force "$WT" 2>/dev/null || true; rm -rf "$WT"
    log "apply abort: target $(short "$NEW") failed validation"; card "Update aborted: $(short "$NEW") failed validation."; return 3
  fi
  git -C "$SRC_DIR" worktree remove --force "$WT" 2>/dev/null || true; rm -rf "$WT"

  # Snapshot user state before promoting (belt-and-suspenders; refresh already preserves it).
  SNAP="$PROFILE_DIR/.snapshots/$(date -u +%Y%m%d-%H%M%S)"
  mkdir -p "$SNAP"
  for x in memory custom env; do
    [ -e "$PROFILE_DIR/$x" ] && cp -R "$PROFILE_DIR/$x" "$SNAP/" 2>/dev/null || true
  done

  # Promote: ff-merge the checkout, then refresh the live profile.
  if git -C "$SRC_DIR" merge --ff-only --quiet "origin/$CHANNEL" \
     && bash "$SRC_DIR/install.sh" --refresh >/dev/null 2>&1 \
     && post_verify; then
    rm -f "$PENDING"
    log "APPLIED $(short "$OLD") -> $(short "$NEW") on $CHANNEL"
    card "Update applied: now on $(short "$NEW") ($CHANNEL). Your memory and custom skills are untouched."
    return 0
  fi

  # Rollback: restore the previous commit + profile + snapshot, and stop the loop.
  log "PROMOTE FAILED — rolling back to $(short "$OLD")"
  git -C "$SRC_DIR" checkout --quiet "$OLD" 2>/dev/null || git -C "$SRC_DIR" reset --hard "$OLD" >/dev/null 2>&1 || true
  bash "$SRC_DIR/install.sh" --refresh >/dev/null 2>&1 || true
  for x in memory custom env; do
    [ -e "$SNAP/$x" ] && cp -R "$SNAP/$x" "$PROFILE_DIR/" 2>/dev/null || true
  done
  printf '%s rolled back from %s to %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(short "$NEW")" "$(short "$OLD")" > "$ROLLBACK_FLAG"
  rm -f "$PENDING"
  log "ROLLED BACK to $(short "$OLD")"
  card "Auto-update reverted to $(short "$OLD") after a failed check. No data lost. Will retry only after review."
  return 5
}

cmd_auto() { cmd_check && cmd_apply; }

cmd_status() {
  ensure_git || return 1
  printf 'channel:   %s\n' "$CHANNEL"
  printf 'HEAD:      %s\n' "$(short HEAD)"
  printf 'pending:   %s\n' "$([ -f "$PENDING" ] && cat "$PENDING" || echo none)"
  printf 'rollback:  %s\n' "$([ -f "$ROLLBACK_FLAG" ] && cat "$ROLLBACK_FLAG" || echo none)"
}

main() {
  local sub="${1:-check}"
  case "$sub" in
    check|apply|auto) acquire_lock; "cmd_$sub" ;;
    status) cmd_status ;;
    clear-rollback) rm -f "$ROLLBACK_FLAG"; echo "rollback flag cleared" ;;
    -h|--help) sed -n '2,30p' "${BASH_SOURCE[0]}" ;;
    *) printf 'usage: self-update.sh [check|apply|auto|status|clear-rollback]\n' >&2; exit 2 ;;
  esac
}

main "$@"
