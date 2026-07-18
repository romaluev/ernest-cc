---
name: ernest-watch
description: Use for ambient watch runs and standing concerns. Detect and remind only; never draft email, CRM, Slack, calendar, or sheet content in watch mode.
version: 1.1.0
---

# Ernest Watch

Run configured standing concerns and produce short reminder cards.

## Non-Negotiable Rules

- Remind only.
- Do not draft external content.
- Do not mutate HubSpot, Gmail, Slack, Calendar, Sheets, or any external system.
- Use real data only. If a connector or brain tool is unavailable, mark the concern skipped.
- Each card must include source references and a `draft_trigger`.

## Input

Read `memory/standing-concerns.md` and `ernest.yaml -> watchers`.

## Data Source Order

Use the first available source:

1. VPS brain MCP when configured:

- `mcp__ernest-brain__health`
- `mcp__ernest-brain__search_mail`
- `mcp__ernest-brain__search_hubspot`
- `mcp__ernest-brain__search_slack`
- `mcp__ernest-brain__write_watch_card`

2. Local MCP connectors in local-only mode.
3. Exported files under `data/mail`, `data/hubspot`, and `data/calendar`.

If using exported files, label every item `source: local-export`. If no real data source exists, use `data/mail/sample-thread.md` only for a clearly labeled demo card.

## Run Sequence

0. **Read threads** — run `ernest read --owed` or `/ernest-read` so watch/draft use full
   message bodies (email, Slack, etc.), not metadata alone.

1. Parse enabled `concerns`.
2. For each concern, load the named playbook and run only its Watch half.
3. Write one card per non-empty result to the configured watch card directory or `mcp__ernest-brain__write_watch_card`.
4. If all concerns are clean, reply `[SILENT]`.

**Deep audit exception:** When the CEO requests a long-window owed-reply audit
(e.g. "full year", "back catalog", "don't stop at this week"), use
`mail-deep-audit` / `/ernest-audit` — not the daily watch loop. Complete every
date chunk in the manifest before summarizing.

## Canonical Reminder Card (the ONE format — all skills reference this)

This is what the engine actually writes (`ernest/watch.py`); model-written cards
must match it so `ernest render` and the brief read them identically. Transcribed
from a real run:

```markdown
# Watch: dropped-followups (2026-06-25)

type: reminder-card
source: local-export
items: 2

Remind/assign only. Say "draft these" if you want draft-only outreach prepared.

## 1. [TIER-1] Lucas Silva - Apex Bank
- tier: tier-1
- waiting: 31d
- why: Inbound 31d ago with no reply (threshold 7d).
- action: Reply to this contact to keep the thread alive.
- context: <one-line summary>
- thread_id: <id>
```

Field contract per item: `## N. <title>` (a `[TIER-N]`/`[OVERDUE]` badge in the
title when tiered), then bullets in this order — optional `- tier:`, optional
`- waiting: Nd`, required `- why:` and `- action:`, optional `- context:` and
`- thread_id:`. Header: `type: reminder-card`, `source:` (`local-export` |
`vps-brain` | `engine-health`), `items: N`.

Skill-specific EXTRA bullets are allowed after the standard ones (keep them
kebab-short): `- checked: mail,slack,hubspot,calendar` (cross-check trail),
`- crm: PROPOSE <update>` (stale-CRM proposal, never auto-applied),
`- assignee: <owner>` (assignment cards), `- list: <name>` (list-sync).

Model-written cards (and every chat summary of a card) end with:

`Reply draft these when you want me to prepare actions.`

Grade cards add score + confidence inline: `- tier: tier-1 (confidence: high,
match score: 100)` plus `- check:` flag lines — see the grading skills.
