---
name: morning-brief
description: Use for /ernest-brief and weekday 08:00 brief runs. Summarizes only what needs the CEO today. Remind-only; no drafts or external writes.
version: 1.0.0
---

# Morning Brief

Create a short, executive brief for the CEO from the last 24 hours of watch cards plus live inbox/calendar/HubSpot state.

## Rules

- Remind-only.
- No drafts.
- No external writes.
- If no action is needed, return `[SILENT]`.
- Prioritize by relationship importance, deadline, and reputational risk.

## Inputs

```yaml
window: "24h"
include:
  - watch_cards
  - inbox
  - calendar
  - hubspot
  - open_promises
```

## Data Source Order

Use the first available source:

- `mcp__ernest-brain__list_watch_cards`
- `mcp__ernest-brain__search_mail`
- `mcp__ernest-brain__search_hubspot`
- `mcp__ernest-brain__search_memory`

If the VPS brain is not configured, use local MCP connectors. If local connectors
are not configured, read exported files under `data/mail`, `data/hubspot`, and
`data/calendar`. Label those outputs `source: local-export`.

Deterministic baseline: `ernest brief` composes this exact brief from the same
source order with no model required. Run it directly for the offline/headless
path, or read its output and enrich it with live reasoning when connectors exist.

## Output Format

```markdown
# Ernest Brief - <date>

## Needs CEO Today
- <item> — owner, source, recommended next action

## Watch
- <item> — why it matters

## Calendar / Prep
- <meeting> — prep needed

## Draft Triggers
- Reply `draft these` to any card when you want me to prepare actions.
```

Keep the brief under 600 words unless the CEO asks for detail.
