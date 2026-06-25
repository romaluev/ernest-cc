# Ernest on Claude Code

Native Claude Code/Cowork bootstrap for Ernest, the draft-first CEO operating
clone.

This package is designed to install with one command, configure the CEO's local
Claude surface, work without the Ernest VPS by default, optionally connect to the VPS Ernest brain, and ship with
three working automations out of the box:

- Morning brief.
- Dropped follow-up recovery.
- Inbox / inbound prospect follow-up.

The CEO should not edit JSON, cron files, or connector config manually. Use
`install.sh` or `install.ps1`, then authorize accounts when prompted.

## Verify it works in 30 seconds

A standard-library engine backs the core flow, so it runs with no model and no
connectors:

```bash
./install.sh
~/.ernest-cc/bin/ernest doctor
~/.ernest-cc/bin/ernest onboard --non-interactive --company "UnicornCo"
~/.ernest-cc/bin/ernest watch && ~/.ernest-cc/bin/ernest brief
~/.ernest-cc/bin/ernest draft --concern dropped-followups
```

This produces real watch cards, a morning brief, and labeled draft-only
outreach from the sample data in `data/`. The Claude Code skills and slash
commands are the natural-language layer on top of these same commands.

## Modes

- **Local-only**: default. Uses local memory, exported data under `data/**`,
  and explicitly reviewed local MCP connectors.
- **VPS brain**: optional. Memory and app tokens live on the VPS; local Claude
  Code/Cowork talks to the brain over remote MCP.

## Safety

Ernest is draft-first. `hooks/pre_tool_use.py` blocks live external sends,
posts, CRM mutations, calendar mutations, and risky filesystem writes before
Claude can execute them.
