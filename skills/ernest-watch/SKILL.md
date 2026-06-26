---
name: ernest-watch
description: Use for ambient watch runs and standing concerns. Detect and remind only; never draft email, CRM, Slack, calendar, or sheet content in watch mode.
version: 1.0.0
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

## Reminder Card Schema

```yaml
reminder_card:
  id: "<concern-id>"
  playbook: "<skill-name>"
  detected_at: "<iso8601>"
  summary: "<one line>"
  items:
    - source: "<gmail-thread | hubspot-record | slack-thread>"
      title: "<human-readable item>"
      owner: "<owner or unknown>"
      days_stalled: "<number or unknown>"
      next_action: "<recommended next action>"
  suggested_next: "<what the draft half would do>"
  draft_trigger: "draft these"
  draft_params: {}
```

End chat/card summaries with:

`Reply draft these when you want me to prepare actions.`
