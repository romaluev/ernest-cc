#!/usr/bin/env bash
# One-command setup. Assume the person running this knows nothing about the tool
# and should not have to.
#
#   ./install.sh                install, verify, first report, daily schedule
#   ./install.sh --no-daily     skip the schedule
#   ./install.sh --uninstall    remove the schedule and the skill links
#
# No pip, no npm, no vendor SDK. Python standard library only.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$HOME/.claude/skills"

DO_CRON=1
UNINSTALL=0
for arg in "$@"; do
  case "$arg" in
    --no-daily) DO_CRON=0 ;;
    --daily)    DO_CRON=1 ;;
    --uninstall) UNINSTALL=1 ;;
  esac
done

GAPS=()
step() { printf '  [%s] %s\n' "$1" "$2"; }
gap()  { GAPS+=("$1"); }

# --- uninstall: everything this ever wrote outside its own folder ------------
if [ "$UNINSTALL" -eq 1 ]; then
  echo ""
  PLIST="$HOME/Library/LaunchAgents/com.linkedin-inbound.triage.plist"
  if [ -f "$PLIST" ]; then
    launchctl unload "$PLIST" >/dev/null 2>&1
    rm -f "$PLIST" && step ok "schedule removed"
  elif [ "$(uname)" != "Darwin" ] && crontab -l 2>/dev/null | grep -Fq "$HERE/linkedin_triage.py"; then
    crontab -l 2>/dev/null | grep -Fv "$HERE/linkedin_triage.py" | crontab - 2>/dev/null \
      && step ok "schedule removed"
  else
    step "--" "no schedule to remove"
  fi
  for s in linkedin-invitations linkedin-inbox; do
    if [ -L "$SKILL_DIR/$s" ]; then rm -f "$SKILL_DIR/$s"; step ok "unlinked skill $s"; fi
  done
  echo ""
  echo "Done. Delete this folder and nothing of it remains."
  echo "Your reports in ~/Documents/LinkedIn-Inbound/ are left alone."
  exit 0
fi

echo ""
if [ -f "$HERE/BUILD.txt" ]; then
  echo "LinkedIn inbound triage — $(sed -n 1p "$HERE/BUILD.txt")"
  sed -n '2,4p' "$HERE/BUILD.txt" | sed 's/^/  /'
else
  echo "LinkedIn inbound triage — setup"
fi
echo "==============================="

# --- python ------------------------------------------------------------------
command -v python3 >/dev/null 2>&1 || {
  echo "python3 not found." >&2
  echo "On macOS: run \`xcode-select --install\` and try again." >&2
  exit 10; }
PYV="$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
python3 -c 'import sys;sys.exit(0 if sys.version_info>=(3,9) else 1)' \
  || { echo "python3 $PYV is too old (need 3.9+)." >&2; exit 10; }
step ok "python3 $PYV"

chmod +x "$HERE/linkedin_triage.py" "$HERE/adapters/linkedin"/*.py 2>/dev/null || true

# --- make the skills reachable from Claude Code ------------------------------
# Symlinks, not copies: the skill and the code it describes stay in step, and
# `--uninstall` removes them. This is the only thing written outside this folder
# besides the reports themselves, and it is two links.
if mkdir -p "$SKILL_DIR" 2>/dev/null; then
  linked=0
  for s in linkedin-invitations linkedin-inbox; do
    [ -d "$HERE/skills/$s" ] || continue
    if [ -e "$SKILL_DIR/$s" ] && [ ! -L "$SKILL_DIR/$s" ]; then
      gap "$SKILL_DIR/$s already exists and is not a link — left it alone."
      continue
    fi
    ln -sfn "$HERE/skills/$s" "$SKILL_DIR/$s" && linked=$((linked+1))
  done
  [ "$linked" -gt 0 ] && step ok "$linked skill(s) available in Claude Code (/linkedin-invitations, /linkedin-inbox)"
else
  gap "Could not write $SKILL_DIR — the skills still work, just run linkedin_triage.py directly."
fi

# --- prove the pipeline on the shipped examples ------------------------------
DEMO_OUT="$(python3 "$HERE/linkedin_triage.py" --demo 2>&1)"
printf '%s' "$DEMO_OUT" | grep -q "invitations.md" \
  && step ok "invitations pipeline verified" \
  || { step "--" "the invitations pipeline produced nothing"
       gap "Run \`python3 linkedin_triage.py --demo\` and read the error."; }
printf '%s' "$DEMO_OUT" | grep -q "messages.md" \
  && step ok "DM pipeline verified" \
  || { step "--" "the DM pipeline produced nothing"
       gap "Run \`python3 linkedin_triage.py --demo\` and read the error."; }

# --- the guarantees ----------------------------------------------------------
for t in "$HERE"/tests/test_*.py; do
  [ -e "$t" ] || continue
  PYTHONPATH="$HERE" python3 "$t" >/dev/null 2>&1 \
    && step ok "$(basename "$t" .py) passes" \
    || { step "--" "$(basename "$t" .py) FAILED"; gap "A guarantee is broken: PYTHONPATH=$HERE python3 $t"; }
done

# --- schedule ----------------------------------------------------------------
# launchd on macOS, cron elsewhere. NOT cron on macOS: `crontab` there trips a
# Full Disk Access prompt and then blocks on it forever with no output, which is
# indistinguishable from a hang and is exactly the thing nobody should have to
# debug. A per-user LaunchAgent needs no special permission.
PLIST="$HOME/Library/LaunchAgents/com.linkedin-inbound.triage.plist"
if [ "$DO_CRON" -eq 1 ]; then
  if [ "$(uname)" = "Darwin" ]; then
    mkdir -p "$HOME/Library/LaunchAgents" 2>/dev/null
    {
      printf '%s\n' '<?xml version="1.0" encoding="UTF-8"?>'
      printf '%s\n' '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">'
      printf '%s\n' '<plist version="1.0"><dict>'
      printf '%s\n' '  <key>Label</key><string>com.linkedin-inbound.triage</string>'
      printf '%s\n' '  <key>ProgramArguments</key><array>'
      printf '%s\n' '    <string>/bin/sh</string><string>-c</string>'
      printf '    <string>cd %s &amp;&amp; LI_UNATTENDED=1 python3 %s/linkedin_triage.py &gt;&gt; %s/triage.log 2&gt;&amp;1</string>\n' "'$HERE'" "'$HERE'" "'$HERE'"
      printf '%s\n' '  </array>'
      printf '%s\n' '  <key>StartCalendarInterval</key><array>'
      for d in 1 2 3 4 5; do
        printf '    <dict><key>Weekday</key><integer>%s</integer><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>\n' "$d"
      done
      printf '%s\n' '  </array>'
      printf '%s\n' '  <key>RunAtLoad</key><false/>'
      printf '%s\n' '</dict></plist>'
    } > "$PLIST"
    launchctl unload "$PLIST" >/dev/null 2>&1
    if launchctl load "$PLIST" >/dev/null 2>&1; then
      step ok "scheduled weekdays at 08:00 (remove: ./install.sh --uninstall)"
    else
      step "--" "could not load the LaunchAgent"
      gap "Run it yourself when you want a report: python3 linkedin_triage.py"
    fi
  else
    LINE="0 8 * * 1-5 cd \"$HERE\" && LI_UNATTENDED=1 python3 \"$HERE/linkedin_triage.py\" >> \"$HERE/triage.log\" 2>&1"
    if crontab -l 2>/dev/null | grep -Fq "$HERE/linkedin_triage.py"; then
      step ok "daily 08:00 run already scheduled"
    elif (crontab -l 2>/dev/null; echo "$LINE") | crontab - 2>/dev/null; then
      step ok "scheduled weekdays at 08:00 (remove: ./install.sh --uninstall)"
    else
      step "--" "could not write the crontab"
      gap "Run it yourself when you want a report: python3 linkedin_triage.py"
    fi
  fi
else
  step ok "no schedule installed (--no-daily)"
fi

# --- the real run ------------------------------------------------------------
# Last, and only after everything above is known good. This is the step that
# needs a LinkedIn session, so it is also the step that may open a browser and
# ask the person to sign in — once, ever.
echo ""
echo "Fetching your actual LinkedIn data..."
python3 "$HERE/linkedin_triage.py"
RC=$?
echo ""
if [ "$RC" -eq 0 ]; then
  step ok "first report written to ~/Documents/LinkedIn-Inbound/latest/"
else
  step "--" "no report yet — nothing was invented to fill the gap"
  gap "Run \`python3 linkedin_triage.py\`. A browser opens on the LinkedIn sign-in page; sign in once and it finishes on its own. Prefer to do it by hand? docs/manual-fallback.md section A, about a minute."
fi

echo ""
if [ "${#GAPS[@]}" -eq 0 ]; then
  echo "Ready. Open ~/Documents/LinkedIn-Inbound/latest/report.pdf"
  echo "Nothing is ever accepted, ignored, or reported without your approval."
  exit 0
fi
echo "Ready, with ${#GAPS[@]} thing(s) still open:"
for g in "${GAPS[@]}"; do echo "  - $g"; done
exit 1
