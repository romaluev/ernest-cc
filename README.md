# Ernest on Claude Code

Draft-first CEO operating clone for Claude Code/Cowork. Local-first: works with
no VPS, no Composio, and no connectors out of the box. Watches what needs you,
drafts only when you ask, never sends on its own.

## Get started

**In Claude (no terminal) — recommended:** open the plugin browser (**+** / `/`),
install **`ernest-cc`** from the Ernest marketplace, then run **`/ernest-setup`** and
answer ~5 plain questions. New here? Read [how-it-works.md](docs/how-it-works.md) (2 min).

**Terminal (power users / setting up for someone else):**

```bash
./install.sh      # once — checks prereqs, installs, prints your first brief
ernest start      # daily: what needs you (nothing sent)
ernest schedule   # run the morning brief automatically
```

No config editing. By default everything stays on your machine ([docs/privacy.md](docs/privacy.md)).

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
| [docs/quickstart.md](docs/quickstart.md) | Get started (in Claude or terminal) |
| [docs/how-it-works.md](docs/how-it-works.md) | 2-min mental model, with diagrams |
| [docs/examples.md](docs/examples.md) | Copy-paste prompts, simple → complex |
| [docs/privacy.md](docs/privacy.md) | What stays on your machine |
| [docs/updates.md](docs/updates.md) | One-tap, validated, auto-rollback updates |
| [docs/connectors.md](docs/connectors.md) | Live data without Composio |
| [docs/daily-use.md](docs/daily-use.md) | Beyond `start` |
| [docs/add-automation.md](docs/add-automation.md) | Add a new use-case |
| [docs/README.md](docs/README.md) | Full index |

## Modes

- **Local** (default): engine + exports in `data/`, optional native MCP.
- **VPS brain** (optional): remote MCP for memory/connectors on your server.

## Safety

`hooks/pre_tool_use.py` blocks external sends, posts, and CRM mutations before
Claude executes them. See [docs/security.md](docs/security.md).
