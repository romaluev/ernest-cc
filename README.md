# Ernest on Claude Code

Native Claude Code/Cowork bootstrap for Ernest, the draft-first CEO operating
clone.

This package installs with one command, configures the CEO's local Claude
surface, works without the Ernest VPS by default, and optionally connects to the
VPS Ernest brain.

It ships the CEO's real, email-centric use-cases out of the box. Most are
**remind/assign only** — no drafting required:

- **Morning brief** — the one screen of what needs you today.
- **Add a collaborator to B2B threads** — flag intros missing your reliable
  teammate (e.g. Manoj) so they don't get dropped.
- **Candidate follow-up** — surface B2B marketing/sales candidates in the inbox
  and assign reach-out (e.g. Alua/Limon).
- **Important-contact recovery** — important contacts (e.g. Nubank) where a
  follow-up slipped.
- **List sync** — reconcile email contacts against a HubSpot list (Korea/Alvin)
  or a Google Sheet (press/TechCrunch).
- **Sourcing pipeline** — track partnership/hire targets needing outreach.
- **Slack task tracking** — transparent open/overdue tasks by owner.
- **Dropped/inbound follow-ups** — general recovery and inbound prospects.

The CEO should not edit JSON, cron files, or connector config manually. Use
`install.sh` or `install.ps1`, then authorize accounts when prompted.

## One command

```bash
./install.sh
```

That's it. The installer sets everything up and immediately prints what needs
you today — real follow-ups, assignments, and syncs from your data — with no
model and no connectors required.

After that, the only command you need day to day is:

```bash
ernest start
```

(Everything else — `draft`, `new-automation`, `learn` — is optional and
explained in [docs/daily-use.md](docs/daily-use.md).)

## Modes

- **Local-only**: default. Uses local memory, exported data under `data/**`,
  and explicitly reviewed local MCP connectors.
- **VPS brain**: optional. Memory and app tokens live on the VPS; local Claude
  Code/Cowork talks to the brain over remote MCP.

## Safety

Ernest is draft-first. `hooks/pre_tool_use.py` blocks live external sends,
posts, CRM mutations, calendar mutations, and risky filesystem writes before
Claude can execute them.
