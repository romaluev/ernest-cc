---
name: add-collaborator
description: Ensure a designated teammate is on matching email threads (e.g. B2B intros) so follow-ups are not dropped. Remind/assign only.
version: 1.0.0
---

# Add Collaborator To Threads

When the CEO starts threads but a reliable teammate should stay on them, this
playbook flags threads where that person is missing.

## Parameters

```yaml
collaborator: "Alex"        # teammate who should be on these threads
category: "b2b"               # thread category to watch
```

## Watch half

1. Find threads in `category` (mail MCP or `data/mail/`).
2. Flag threads where `collaborator` is not in `participants`.
3. Write a remind/assign card — action is add them to the thread, not draft.

Deterministic: `ernest start` via concern `b2b-collaborator-coverage`.

Adding someone to a live thread is approval-gated.
