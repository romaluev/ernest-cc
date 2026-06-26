# Connectors (no Composio)

Ernest does **not** use Composio. Connectors are optional native MCP servers you
choose and approve — or exported files under `data/` when you want zero third
parties.

## What works without any connector

```bash
./install.sh    # once
ernest start    # every day
```

The engine reads exported mail, CRM lists, sheets, sourcing pipelines, and tasks
from `data/`. No model, no OAuth, no middleman. This is the default and is
enough for remind/assign automations.

## Three ways to get live data

| Approach | Trust model | Setup |
|---|---|---|
| **Exports** | Highest — you control files | Drop CSV/MD exports in `data/` |
| **Native MCP** | Direct — one server per app | Add via installer or `claude mcp add` |
| **VPS brain** (optional) | Tokens on your server | `./install.sh --mode vps` |

Pick one per app. Mixing is fine (e.g. live Gmail MCP + exported HubSpot list).

## Native MCP (recommended when going live)

Each connector is a standard MCP server — not a generic action router:

```text
mcp__gmail__search_threads      find candidates
mcp__gmail__get_thread          read full email thread (required after search)
mcp__gmail__create_draft        draft (allowed)
mcp__gmail__send_email          blocked by gate until CEO approves
mcp__slack__get_thread          read full Slack thread / replies
```

Same pattern for HubSpot, Slack, Google Sheets, Calendar, Teams, etc. **Search
finds; read loads the full conversation.**


**How to add:**

1. Choose a server you trust (official, self-hosted, or Anthropic's built-in OAuth where available).
2. Operator adds it to MCP config during install — the CEO never edits JSON.
3. Ernest uses it read-first; writes and sends stay approval-gated.

See `examples/local-only.mcp.example.json` for the shape. The installer writes
the active config to `~/.ernest-cc/.mcp.json`.

## Per use-case

| Automation | Offline (`data/`) | Live (native MCP) |
|---|---|---|
| Dropped follow-ups | `data/mail/` (full threads) | Gmail MCP: search + **get_thread** |
| Slack owed replies | `data/slack/threads/` | Slack MCP: search + **get_thread** |
| Important contacts (tier) | mail + `data/hubspot/` | Mail + HubSpot MCP |
| Add collaborator to threads | mail with `participants` | Mail MCP |
| Candidate follow-up | mail with `category: candidate` | Mail MCP |
| List sync (CRM / sheet) | `data/lists/*.csv` | HubSpot or Sheets MCP |
| Sourcing pipeline | `data/sourcing/targets.csv` | Search MCP (optional) |
| Slack task tracking | `data/slack/tasks.csv` | Slack MCP (read channels) |

## VPS brain (optional)

If you use a VPS, connectors can live there instead of on the CEO's laptop.
Local Claude Code talks to one remote MCP (`ernest-brain`). See [vps-brain.md](vps-brain.md).

Composio is **not** part of this stack. The old Hermes-based Ernest used it;
**ernest-cc** deliberately does not.
