# Ernest on Claude Code

Draft-first CEO operating clone for Claude Code/Cowork. Local-first: works with
no VPS, no Composio, and no connectors out of the box.

## Install and run

```bash
./install.sh      # once — prints your first brief
ernest start      # daily
```

No config editing. Prompts: [docs/examples.md](docs/examples.md).

## What it does

Remind/assign automations over email (and optional Slack tasks). Drafts only
when you ask; the gate blocks sends and live CRM writes. Answers stay **short and
consistent** (Bottom line + Read-more digest) and **adapt to your taste** over
time (`memory/preferences.md`).

| Automation | Purpose |
|---|---|
| Morning brief | One screen of open loops |
| Follow-up recovery | Threads and VIP-tier slips |
| Collaborator coverage | Threads missing a designated teammate |
| Candidate routing | Inbox hires → assign owners |
| List sync | Email vs CRM list or spreadsheet |
| Sourcing pipeline | Targets needing outreach |
| Task tracking | Open/overdue by owner |
| Inbound prospects | Partnership/sales leads waiting |

## Connectors

Optional. Native MCP servers or file exports under `data/` — not Composio.
Details: [docs/connectors.md](docs/connectors.md).

## Documentation

| Doc | Purpose |
|---|---|
| [docs/quickstart.md](docs/quickstart.md) | Install + daily use |
| [docs/examples.md](docs/examples.md) | Copy-paste prompts |
| [docs/connectors.md](docs/connectors.md) | Live data without Composio |
| [docs/daily-use.md](docs/daily-use.md) | Beyond `start` |
| [docs/add-automation.md](docs/add-automation.md) | Scale |
| [docs/README.md](docs/README.md) | Full index |

## Modes

- **Local** (default): engine + exports in `data/`, optional native MCP.
- **VPS brain** (optional): remote MCP for memory/connectors on your server.

## Safety

`hooks/pre_tool_use.py` blocks external sends, posts, and CRM mutations before
Claude executes them. See [docs/security.md](docs/security.md).
