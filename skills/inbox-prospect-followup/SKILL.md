---
name: inbox-prospect-followup
description: Watch for inbox threads matching a saved prospect/profile and needing follow-up. Draft only on explicit ask; never sends without approval.
version: 1.0.0
---

# Inbox Prospect Follow-Up

Find people in the CEO's inbox who match a target profile and need a follow-up.

## Parameters

```yaml
profile: "inbound B2B and partnerships"
intent: "sales | partnership | hire | press | investor"
window: "90d"
min_signal: "1 real exchange"
dedupe_against: ""  # optional HubSpot list, owner, or pipeline
card_id: ""
```

## Watch Half

1. Search mail for people matching `profile` and `intent` within `window`.
   - VPS mode: use `mcp__ernest-brain__search_mail`.
   - Local MCP mode: use configured local mail tools.
   - Export fallback: read `data/mail/**`; label output `source: local-export`.
2. Require `min_signal` so Ernest does not hallucinate cold prospects.
3. Dedupe against HubSpot when available, or `data/hubspot/**` in export fallback mode.
4. Flag people with no CEO follow-up or a stalled next step.
5. Write a ranked reminder card with last-exchange summaries.

No drafts in watch mode.

## Draft Half

Use only after explicit ask or `draft these`.

1. Load card items or re-run the search.
2. Pull thread context, HubSpot context, and relevant CEO voice exemplars.
3. Draft concise replies referencing the actual prior exchange.
4. Include a clear ask or next step.
5. Batch drafts for approval.

Never send. Never create/update HubSpot records without approval.
If drafting from exported data, clearly state that the draft must be checked against the live inbox before sending.

## Reminder Card Output

```yaml
reminder_card:
  id: "inbox-prospects"
  playbook: "inbox-prospect-followup"
  summary: "<N prospects need follow-up>"
  items:
    - person:
      source_thread:
      last_exchange:
      why_matched:
      recommended_next:
  draft_trigger: "draft these"
```

## When Not To Use

Do not use for broad cold prospecting with no thread history.
