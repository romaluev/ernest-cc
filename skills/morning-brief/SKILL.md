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
  - calendar          # today's meetings; flag which need call-prep
  - hubspot           # deals: closing this week, no next step, stalled, stage changes <24h
  - inbox             # important unanswered (clients/partners first)
  - slack             # mentions / DMs needing action
  - calls             # Fireflies: yesterday's call summaries + action items
  - notion            # weekly initiatives/goals owned by the CEO
  - open_promises
```

## Data Source Order

Use the first available source (connectors are swappable):

- VPS brain: `mcp__ernest-brain__list_watch_cards`, `search_mail`, `search_hubspot`, `search_memory`.
- Live native MCP: Google Calendar, HubSpot, Gmail, Slack, Fireflies (or Gong), Notion.
- Export fallback: `data/mail`, `data/hubspot`, `data/calendar`, `data/calls`, `data/notion`.
  Label those outputs `source: local-export`.

If a source is not connected, include the sections you can and note which inputs
were unavailable — don't drop the brief.

Deterministic baseline: `ernest brief` composes this exact brief from the same
source order with no model required. Run it directly for the offline/headless
path, or read its output and enrich it with live reasoning when connectors exist.

## Output Format

Chat stays short (house format): **Bottom line** (the single most important
thing today) + **Top 3 actions**, then **Read more →** the rendered digest. The
full brief uses this fixed order:

```markdown
# Ernest Brief - <date>

## Bottom line
- <the one thing that matters most today>

## Today's calendar
- <time> <meeting> — flag [needs call-prep] where relevant

## Top 3 actions
- <highest-leverage moves on revenue/relationships>

## Deals needing attention
- <closing this week / no next step / stalled 7d+ / stage change> (HubSpot)

## Unanswered
- <important mail + Slack to reply to — one line of context each>

## Open follow-ups from yesterday
- <promises made, not yet kept>

## Yesterday's calls
- <Fireflies summary + action items owned by the CEO>

## Reminders
- <weekly initiatives / events from Notion>

## Draft triggers
- Reply `draft these` to any card when you want me to prepare actions.
```

Omit any section with no items. Keep the full brief under 600 words; the chat
summary far shorter. Remind-only — never draft or write here.
