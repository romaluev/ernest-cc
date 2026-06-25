---
name: account-followup-recovery
description: Watch for dropped follow-ups on one account or all important contacts. Draft recoveries only on explicit ask or draft-trigger.
version: 1.0.0
---

# Account Follow-Up Recovery

Find stalled threads, quiet deals, and unmet promises. In watch mode, write reminder cards only. In draft mode, prepare recovery drafts for approval.

## Parameters

```yaml
account: "*"        # company, person, or all priority contacts
staleness: "7d"
window: ""          # optional max lookback, e.g. "365d" for deep audits
include: "threads,deals,promises"
card_id: ""         # optional reminder card to draft from
```

For a **full back-catalog sweep** (e.g. one year), use `mail-deep-audit` or
`/ernest-audit` instead of the daily watch defaults. Set `window` when the CEO
names a bounded period.

## Watch Half

Use when running `/ernest-watch`, scheduled watch, or a CEO asks "where did I drop the ball?"

1. Resolve `account`.
2. Search mail and HubSpot for open threads, quiet deals, and promises past `staleness`.
   - VPS mode: use `mcp__ernest-brain__search_mail` and `mcp__ernest-brain__search_hubspot`.
   - Local MCP mode: use configured local mail/CRM tools.
   - Export fallback: read `data/mail/**` and `data/hubspot/**`; label output `source: local-export`.
3. Rank by relationship tier, days stalled, promise risk, and deal/hire importance.
4. Produce reminder cards only.

Do not draft in watch mode.

## Draft Half

Use only when the CEO asks directly or says `draft these`.

1. Load the reminder card or re-run the search.
2. Retrieve the last real exchange and relationship context.
3. Retrieve voice exemplars from memory/sent mail if available.
4. Draft one recovery message per item.
5. Include facts used and uncertainties.
6. Batch for CEO approval.

Never send. Never update HubSpot stages directly.
If drafting from exported data, clearly state that the draft is based on local exported files and should be verified against the live thread before sending.

## Draft Output

```markdown
## Draft Batch: Follow-Up Recovery

### <contact / account>
Source: <thread/deal/promise reference>
Why now: <reason>
Confidence: <high/medium/low>

Draft:
<message>

Grounding:
- <fact/source>

Needs approval:
- Send email
- Optional HubSpot note/stage proposal
```

## When Not To Use

Do not use for cold outreach with no prior exchange. Use a sourcing skill instead.
