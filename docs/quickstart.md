# Quickstart

## Install (one command)

```bash
./install.sh
```

The installer:

- Copies Ernest to `~/.ernest-cc`
- Puts `ernest` on your PATH (when possible)
- Runs the first brief immediately — you see what needs attention without another step

No config files to edit. No Composio. No connectors required.

## Every day

```bash
ernest start
```

Refreshes watch cards and prints the morning brief. Remind/assign only — nothing
is sent.

## Optional: Claude Code

For live Gmail/HubSpot/Slack (instead of exported files):

1. Open `~/.ernest-cc` in Claude Code.
2. Run `/ernest-onboard` once to connect accounts.
3. Use prompts from [examples.md](examples.md).

You do not need Claude for daily value — `ernest start` works alone.

## Optional: VPS brain

Only if canonical memory and connector tokens should live on a remote server:

```bash
ERNEST_BRAIN_URL="https://your-server/mcp" \
ERNEST_BRAIN_TOKEN="..." \
./install.sh --mode vps
```

See [vps-brain.md](vps-brain.md). Local mode is the default.

## What you see after install

Sample data ships with the package so the first run is real, not empty:

- dropped and VIP-tier follow-ups
- B2B threads missing a designated collaborator
- inbox candidates to assign
- email vs CRM list / sheet gaps
- sourcing targets and open tasks

Replace sample files under `data/` with your exports, or connect native MCP
servers — see [connectors.md](connectors.md).

## Update without losing memory

```bash
git pull --ff-only && ./install.sh --refresh
```
