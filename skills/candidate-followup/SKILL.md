---
name: candidate-followup
description: Find inbox candidates (any role) with no follow-up and assign reach-out to named owners. Remind/assign only.
version: 1.0.0
---

# Candidate Follow-Up

Surfaces hiring candidates sitting in the inbox and assigns owners to reach out.

## Parameters

```yaml
role: "B2B marketing/sales"
assignees: "recruiting-lead, sales-lead"
window: "180d"
```

## Watch half

1. Find threads with `category: candidate` or `intent: hire`.
2. Flag those still owed a reply within `window`.
3. Card lists each candidate with assignees from config.

Deterministic: concern `b2b-candidates`. Optional draft half on explicit ask only.
