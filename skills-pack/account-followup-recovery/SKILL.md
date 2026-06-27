---
name: account-followup-recovery
description: Find genuinely-dropped follow-ups across ALL the CEO's tools (mail, Slack, HubSpot, calendar) — and suppress anything already handled elsewhere. Watch/remind by default; draft recoveries + CRM-update proposals only on explicit ask. First sweep covers 12 months, then incremental.
version: 2.0.0
---

# Account Follow-Up Recovery

Find stalled threads, quiet deals, and unmet promises — but **only the ones that are
truly still open.** The #1 way this skill loses trust is flagging a "dropped"
follow-up that was actually resolved somewhere else. So the rule is: **search wide,
then cross-check for resolution before reporting.**

## Time window (cold-start → incremental)

- If the CEO names a period ("last 90 days", "this quarter"), use it.
- Otherwise run `ernest audit` (no `--window`) — it auto-picks the window:
  **first-ever sweep = last 12 months**; every later sweep = **only since the last
  sweep** (so repeats are fast). It writes a dated manifest; follow it.

## Watch Half (remind-only)

Use on `/ernest-watch`, scheduled watch, or "where did I drop the ball?".

### 1. Find candidates across EVERY connected tool (not just mail)
Read full threads, not snippets (`read-thread` / `ernest read`).
- **Mail** (Outlook/Gmail): threads where they wrote last and you never replied.
- **HubSpot**: quiet/overdue deals, open tasks, contacts past next-touch.
- **Slack**: open asks / threads you owe a reply on.
- **Calendar**: things you promised to schedule but never did.
Dedupe by contact/company/thread *across* tools.
(VPS mode: `mcp__ernest-brain__search_mail`/`search_hubspot`/`search_slack` then the
matching `read_*_thread`. Local MCP: the configured tools. Else `data/**` exports,
labeled `source: local-export`.)

### 2. CROSS-CHECK each candidate for resolution — before flagging it
For every candidate, look in the *other* tools to see if it was already handled:
- **HubSpot:** deal advanced/closed, or recent activity logged?
- **Slack:** resolved or confirmed in a thread/DM? (search the company, person, topic)
- **Calendar:** did the meeting actually happen?
- **Mail:** did you (or a teammate) reply in a *different* thread?

> Example: you emailed Mahi about the meeting with Rene; that mail thread looks
> unanswered — but on Slack Mahi confirmed he met Rene. **That is resolved. Do NOT
> report it as a dropped follow-up.**

If it was handled elsewhere → **drop it from the list.**

### 3. Stale CRM → propose an update (don't write)
If something was resolved elsewhere but **HubSpot doesn't reflect it** (deal stage,
next-step, logged activity), add a **proposed HubSpot update** to the card — a
reviewable, draft-first action. Never write to the CRM automatically.

### 4. Surface only genuinely-open items
Rank by relationship tier, days waiting, deal/hire value, promise risk. Exclude
noise (newsletters, job-seeker intros, cold vendor) unless asked. Reminder cards
only — no drafts, no sends, no live CRM writes in watch mode.

## Draft Half (only on `draft these` / direct ask)

1. Load the card or re-run the search (with the same cross-check).
2. Retrieve the last real exchange + relationship context + voice exemplars.
3. Draft one recovery message per **still-open** item.
4. For any **stale-CRM** item, prepare the proposed HubSpot update too (separate, gated).
5. State facts used + uncertainties. Batch for approval. **Never send. Never write CRM directly.**

## Output (watch card)

```markdown
## <contact / account>  ·  tier: <t>  ·  waiting: <Nd>
- why open: <reason>  (source: <thread/deal/promise>)
- checked: mail ✓ · slack ✓ · hubspot ✓ · calendar ✓  → not resolved elsewhere
- action: reply / loop-in / schedule
- crm: <"up to date" | "PROPOSE: set stage=… / log activity (needs approval)">
```

## When Not To Use

Cold outreach with no prior exchange → use a sourcing skill. Don't report items you
confirmed were handled elsewhere — suppress them (optionally note "N resolved elsewhere").
