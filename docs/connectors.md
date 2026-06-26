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
| Call prep | `data/hubspot/`, `data/calls/` | HubSpot + Fireflies + Clay/Apollo + web |
| Call coaching | `data/calls/` | Fireflies (or Gong) + HubSpot + Notion |
| Support triage | `data/support/` | Pylon + Zendesk + Intercom (Fin) + Slack |
| Hiring pipeline | `data/ashby/` | Ashby + Calendar + Gmail/Slack + Notion |
| Lead enrichment | `data/enrichment/` | Clay + Apollo + HubSpot |
| Deal desk (contracts) | `data/notion/` (dry run) | HubSpot + Ironclad (via MATIC) + Notion |

## Northwind stack map (flexible / swappable)

Connectors are a swappable layer — point a skill at whatever tool you use. This
maps the current Northwind stack and the open gaps. Reads/searches are used
freely; **sends, posts, CRM/contract writes stay approval-gated**.

| Function | Tool (Northwind) | Ernest use | Status |
|---|---|---|---|
| CRM / source of truth | HubSpot | canonical contacts, deals, stages | live-capable |
| Lead routing | HubSpot automations | watch + assign | live-capable |
| Enrichment | Clay + Apollo | `lead-enrichment` → grading | live-capable |
| Call recording | Fireflies | `call-prep`, `call-coaching` | live-capable |
| Coaching | — (gap) | `call-coaching` builds the layer | new |
| Contracts (CLM) | Ironclad (+ MATIC) | `deal-desk` pilot, L3-gated | pilot |
| Comms | Slack | routing, owed replies, approvals | live-capable |
| Support self-serve | Intercom Fin (testing) | `support-triage` deflection | evaluating |
| Tickets | Pylon + Zendesk | `support-triage` | live-capable |
| Knowledge / policy | Notion | positioning, policy, playbooks | live-capable |
| Data warehouse | Hex | metrics on request | optional |
| ATS | Ashby | `hiring-pipeline` | live-capable (no autos yet) |
| Productivity | Google Workspace | Calendar/Gmail in brief + prep | live-capable |
| Orchestration | Claude (connectors) | all of the above | this system |

Open gaps Ernest is built to help close: (1) self-serve routing (Fin pilot),
(2) contracts inside the CRM (HubSpot→Ironclad via MATIC — needs legal sign-off),
(3) coaching/best-practices capture, (4) hiring automation. Each has a skill that
works read-first today and proposes the write/automation step for approval.

## VPS brain (optional)

If you use a VPS, connectors can live there instead of on the CEO's laptop.
Local Claude Code talks to one remote MCP (`ernest-brain`). See [vps-brain.md](vps-brain.md).

Composio is **not** part of this stack. The old Hermes-based Ernest used it;
**ernest-cc** deliberately does not.
