---
name: b2b-lead-grading
description: Grade and sort inbound B2B leads/threads for Higgsfield into Tier-1, Tier-2, or Trash so Alex only sees what matters. Use when triaging inbound email, deciding who to reply to first, qualifying a prospect, or asking "is this worth my time?". Remind/assign only; never auto-reply.
version: 1.0.0
---

# B2B Lead Grading

Sort inbound so Alex spends reply time on Tier-1, Tier-2 is handled efficiently,
and trash never reaches him. Full criteria: `memory/icp-b2b.md`. Quick rubric:
`references/rubric.md`.

## Signal priority (always in this order)

1. **CRM (HubSpot)** — existing tier, deal stage, or prior activity wins.
2. **Curated lists** — `data/grading/b2b-rubric.json`.
3. **Inference** — email content + public knowledge. If you can't confirm a
   Tier-1 claim (e.g. Fortune 500), **flag low confidence**; don't guess.

## Run sequence

1. **Read the full thread** (`read-thread` skill) — grade on what they actually
   said, not a subject line.
2. Get the deterministic starting grade:
   ```bash
   ernest grade --b2b
   ```
   Cards land in `00-Watch/b2b-grades--<date>.md`, sorted Tier-1 first, each with
   reasons + `check:` flags.
3. Resolve every `check:` flag using CRM, the lists, or public knowledge.
   - Conflicting signals → take the **higher** tier and note the conflict.
   - Unknown company, no signal → Tier-2, low confidence, flag for a human check.
4. Produce a remind/assign card. **Never draft or reply in grading mode.**

## Output (per lead)

```yaml
lead:
  who: "<name> — <company>"
  tier: tier-1 | tier-2 | trash
  confidence: high | medium | low
  why: "<decisive signals>"
  action: "Tier-1 -> Alex replies; Tier-2 -> route to owner; Trash -> archive/decline"
  source: "<thread_id / CRM record>"
```

## Hard rules

- Remind/assign only. Drafts happen only on Alex's explicit "draft these".
- Don't downgrade a strategic-but-small account that fits the ICP (e.g. a small
  famous AI studio is Tier-1 on ICP fit, not size).
- Trash is a recommendation to archive/decline — never an auto-send.
