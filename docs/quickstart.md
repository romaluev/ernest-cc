# Quickstart

Ernest should take the CEO from install to first useful card without editing config files.

## Default: Local-Only Mode

```bash
./install.sh
```

This works without the Ernest VPS. The installer creates a local vault, local
memory, local exported-data folders, and an `ernest` CLI launcher.

### Verify in 30 seconds (no model, no connectors)

```bash
~/.ernest-cc/bin/ernest doctor
~/.ernest-cc/bin/ernest onboard            # add --non-interactive --company "..." to script it
~/.ernest-cc/bin/ernest watch
~/.ernest-cc/bin/ernest brief
~/.ernest-cc/bin/ernest draft --concern dropped-followups
```

You should see watch cards in `00-Watch/`, a brief in `00-Daily/`, and labeled
draft-only outreach in `00-Drafts/`. Nothing is ever sent.

Then, for the full assistant experience:

1. Sign in to Claude Code or Claude Desktop.
2. Start Claude Code in `~/.ernest-cc`.
3. Run `/ernest-onboard`.
4. Run `/ernest-brief`.

## Optional: VPS Brain Mode

```bash
ERNEST_BRAIN_URL="https://your-vps.example.com/mcp" \
ERNEST_BRAIN_TOKEN="..." \
./install.sh --mode vps
```

Then:

1. Sign in to Claude Code or Claude Desktop.
2. Authorize Gmail/HubSpot/Slack/Calendar through the links shown by the VPS brain or connector flow.
3. Start Claude Code in `~/.ernest-cc`.
4. Run `/ernest-onboard`.
5. Run `/ernest-brief`.

Use VPS brain mode when the existing Ernest VPS should hold canonical memory and app connector tokens.

## First Useful Moment

After onboarding, Ernest should show:

- a morning brief or dry-run brief
- dropped follow-up cards
- inbound/prospect follow-up cards

Reply `draft these` or run `/ernest-draft` to prepare approval batches.
