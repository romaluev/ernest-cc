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

Optional power commands: see [examples.md](examples.md) and [daily-use.md](daily-use.md).

### Claude Code (optional, richer with live mail/CRM)

When you want Ernest to search live Gmail/HubSpot instead of exported files:

1. Sign in to Claude Code.
2. Open `~/.ernest-cc`.
3. Run `/ernest-onboard` once to connect accounts.
4. Use any prompt from [examples.md](examples.md).

You do **not** need Claude for daily value — `ernest start` works alone.

## Optional: VPS Brain Mode

```bash
ERNEST_BRAIN_URL="https://your-vps.example.com/mcp" \
ERNEST_BRAIN_TOKEN="..." \
./install.sh --mode vps
```

Then authorize Gmail/HubSpot/Slack through the VPS brain and use prompts from
[examples.md](examples.md). Daily terminal use is still just `ernest start`.

Use VPS brain mode only when the Ernest VPS should hold canonical memory and app
connector tokens. Local mode is the default and is enough to demo and use.

## First useful moment

After `./install.sh`, you already see:

- morning brief summary
- B2B threads missing Manoj
- candidates to assign (Alua/Limon)
- important follow-ups (e.g. Nubank)
- Korea / press list sync gaps
- sourcing and Slack task cards

More prompts: [examples.md](examples.md).
