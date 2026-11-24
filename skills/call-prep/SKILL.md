---
name: call-prep
description: Build a one-page prep before a sales, partner, or investor call/meeting. Use when the CEO names an upcoming call, deal, or company ("call prep", "prep me for [company]", "what do I need before the [account] meeting", "brief on the [deal]"), or when a calendar event needs prep. Read-only research; anything outbound stays draft-first.
version: 1.0.0
---

# Call Prep

Produce a tight, decision-ready one-pager before a call. The CEO gives a company,
a HubSpot deal, or a meeting — or you take the next calendar event that needs prep.

## Inputs

```yaml
target: ""          # company name, contact, or HubSpot deal id
meeting: ""         # optional calendar event; else next prep-worthy event
depth: "standard"   # "quick" (CRM+last call) or "deep" (full web research)
```

## Data sources (read-only; connectors are swappable)

Use the first available per source; label provenance (CRM vs web vs call).

| Need | Live connector (any equivalent) | Export fallback |
|---|---|---|
| Deal + company, history, contacts | HubSpot MCP (`search_*`, `get_*`) | `data/hubspot/**` |
| Past calls: summaries, objections, promises | Fireflies (or Gong) MCP | `data/calls/**` |
| Attendee/company enrichment | Clay, Apollo MCP | `data/enrichment/**` |
| Recent comms | Gmail + Slack MCP (`get_thread`) | `data/mail/**`, `data/slack/**` |
| Public signals: raises, launches, hiring, news | Web search | — |
| Our positioning / competitive / policy | Notion MCP | `data/notion/**` |

If a source is missing, say so in the doc instead of guessing. Read full threads
and call transcripts — not snippets (`read-thread` / `ernest read`).

## Run sequence

1. Resolve `target` (or pick the next calendar event needing prep).
2. Pull deal + company state from CRM; read the last real exchange and last call.
3. Enrich attendees (role, seniority, what each cares about).
4. Tier the account with `b2b-lead-grading` when it sharpens prioritization.
5. Gather 2–3 fresh public signals tied to a hypothesis for Northwind.
6. Write the one-pager (see `references/one-pager.md`), then render it
   (`ernest render`) so it's a clean, shareable artifact.

## Output

Chat stays short (house format): **Bottom line** (call goal + the one thing that
wins it), top 2–3 prep points, then **Read more →** the rendered one-pager.
Full structure in `references/one-pager.md`.

## Rules

- Read-only. Never auto-send a pre-read; if the CEO wants one sent, draft it for approval (draft-first).
- Mark every claim's source (CRM / call / web / enrichment). Flag low-confidence items.
- No fabricated names, numbers, or quotes. Missing data is stated, not invented.
- Keep the goal/exit-criteria explicit — a prep doc without a decision is noise.
