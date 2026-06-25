---
name: add-collaborator
description: Ensure a teammate is on the threads that matter (e.g. add Manoj to every B2B intro) so the CEO's intros never get dropped. Remind/assign only.
version: 1.0.0
---

# Add Collaborator To Threads

The CEO's intros get dropped; a reliable teammate does not. This watches a
category of threads and flags any where the named collaborator is missing, so
they can be added before the thread goes cold.

## Parameters

```yaml
collaborator: "Manoj"     # teammate who should be on these threads
category: "b2b"           # thread category to watch (b2b, partnerships, ...)
```

## Watch Half

1. Find threads in `category` (VPS brain -> local mail MCP -> `data/mail/**`).
2. Read each thread's participants.
3. Flag threads where `collaborator` is not a participant.
4. Write one remind/assign card: "Add <collaborator> to these threads."

No drafts. The action is an assignment, not a message.

## Deterministic baseline

`ernest watch` runs this for the `add-manoj-to-b2b` concern with no model. The
card lists each B2B thread missing the collaborator.

## Doing the add

Adding the collaborator to a live thread is an external mutation and stays
approval-gated. Ernest prepares the assignment; the CEO (or an approved action)
adds the person.

## When Not To Use

Do not use to add people to threads outside the configured category, or to add
external parties. This is for internal collaborators only.
