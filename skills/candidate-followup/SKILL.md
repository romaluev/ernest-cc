---
name: candidate-followup
description: Find B2B marketing/sales (or any role) candidates sitting in the inbox with no follow-up, and assign reach-out to a named owner (e.g. Alua, Limon). Remind/assign only.
version: 1.0.0
---

# Candidate Follow-Up

Good candidates reply and then go cold because no one owns the next step. This
finds them and assigns reach-out.

## Parameters

```yaml
role: "B2B marketing/sales"   # the role profile to match
assignees: "Alua, Limon"      # who should reach out
window: "180d"                 # how far back to look
```

## Watch Half

1. Find inbox threads tagged `candidate` or with `intent: hire`
   (VPS brain -> local mail MCP -> `data/mail/**`).
2. Keep those still owed a reply within `window`.
3. Write one card listing each candidate with the assigned owner.

No drafts. The action is "assign reach-out to <assignees>".

## Deterministic baseline

`ernest watch` runs this for the `b2b-candidates` concern with no model.

## Optional draft

If the CEO says "draft these", produce a short, neutral first-touch draft per
candidate for the assignee to review. Never sends.

## When Not To Use

Not for cold candidates with no inbound signal. Use a sourcing pipeline instead.
