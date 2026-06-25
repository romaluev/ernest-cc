# Quickstart

Ernest should take the CEO from install to first useful card without editing config files.

## Default: Local-Only Mode

```bash
./install.sh
```

That single command installs everything and immediately prints what needs you
today, with no model and no connectors. It also puts a short `ernest` command on
your PATH.

### Day to day

```bash
ernest start
```

One command: it refreshes your watch cards and prints the brief. Behind the
scenes that writes cards to `00-Watch/` and the brief to `00-Daily/`. Nothing is
ever sent.

Optional power commands (see [daily-use.md](daily-use.md)): `ernest draft`,
`ernest new-automation`, `ernest learn`.

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
