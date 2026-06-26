---
name: b2b-lead-grading
description: Grade and sort inbound B2B leads/threads into Tier-1, Tier-2, or Trash so the CEO only sees what matters. Use when triaging inbound, deciding who to reply to first, qualifying a prospect, or asking "is this worth my time?". Be generous on real fit, strict on trash; rank by match strength. Remind/assign only; never auto-reply.
version: 1.1.0
---

# B2B Lead Grading

Sort inbound so the CEO spends reply time on Tier-1, Tier-2 is routed, and trash
never reaches them. Company + ICP are config, not hardcoded — read
**`memory/company-core.md`** for the real company and **`memory/icp-b2b.md`** /
**`data/grading/b2b-rubric.json`** for criteria. (Sample names like "Northwind"
mean onboarding hasn't run — ask the user their company + ICP first.)

## Signal priority (always in this order)

1. **CRM** — existing tier, deal stage, or prior activity wins.
2. **Curated lists** — `data/grading/b2b-rubric.json`.
3. **Inference** — content + public knowledge. Can't confirm a Tier-1 claim
   (e.g. market-leader)? **Flag low confidence**; don't guess.

## Grade widely, rank by score (fixes "too narrow / bad sort")

- The rubric lists are a **seed, not a limit.** Recognize ICP fit beyond the
  literal list: a small-but-famous AI studio, a known agency, a real enterprise
  buyer, or genuine enterprise intent all count even if not listed — use public
  knowledge and note it.
- **Don't over-trash.** Only obvious cold vendor/SEO/backlink pitches are trash.
  An ambiguous lead is Tier-2 with a flag, not trash — surface it.
- Sort by the **match score** the engine now emits (Tier first, then score), so
  the strongest leads lead each tier instead of date order.

```bash
ernest grade --b2b
```
Cards land in `00-Watch/b2b-grades--<date>.md`, sorted Tier-1 first, each with
reasons, a match score, and `check:` flags. Read the full thread (`read-thread`)
before finalizing — grade on what they said, not a subject line.

## Output (per lead)

```yaml
lead:
  who: "<name> — <company>"
  tier: tier-1 | tier-2 | trash
  score: <match score>
  confidence: high | medium | low
  why: "<decisive signals>"
  action: "Tier-1 -> CEO replies; Tier-2 -> route to owner; Trash -> archive/decline"
  source: "<thread_id / CRM record>"
```

## Hard rules

- Remind/assign only. Drafts happen only on the CEO's explicit "draft these".
- Conflicting signals → take the **higher** tier and note the conflict.
- A strategic-but-small account that fits the ICP is Tier-1 on fit, not size.
- Trash is a recommendation to archive/decline — never an auto-send.
