---
name: ernest-library-index
description: Use before inventing or adding workflows. Lists Ernest's installed use-cases, their purpose, safety level, and when not to use them.
version: 1.0.0
---

# Ernest Library Index

Use this catalog before choosing or creating a workflow.

## Installed Use-Cases

| Skill | Engine playbook | What it does | Mode |
|---|---|---|---|
| `morning-brief` | (brief) | Today's open loops in one screen | remind-only |
| `account-followup-recovery` | `account-followup-recovery` | Dropped follow-ups; tier-scoped for important contacts (Nubank) | watch + draft |
| `inbox-prospect-followup` | `inbox-prospect-followup` | Inbound prospects with no follow-up | watch + draft |
| `add-collaborator` | `add-collaborator` | Add a teammate (Manoj) to B2B threads missing them | remind/assign |
| `candidate-followup` | `candidate-followup` | B2B marketing/sales candidates to assign (Alua/Limon) | remind/assign |
| `list-sync` | `list-sync` | Reconcile email vs a HubSpot list / Google Sheet (Korea, Press) | remind/assign |
| `sourcing-pipeline` | `sourcing-pipeline` | Track partnership/hire targets needing outreach | remind/assign |
| `slack-task-tracker` | `task-tracker` | Transparent open/overdue tasks by owner | remind/assign |
| `ernest-watch` | (orchestration) | Runs all enabled concerns and writes cards | remind-only |
| `ernest-use-case-author` | (self-improvement) | Adds/improves automations via reviewed proposals | proposal-only |

## Selection Rules

- "what slipped" / "important contacts I owe" -> `account-followup-recovery`.
- "add Manoj to my B2B threads" -> `add-collaborator`.
- "find candidates to reach out to" -> `candidate-followup`.
- "sync my Korea email with the HubSpot list" / "sync the press list" -> `list-sync`.
- "find more people like X for partnerships/hiring" -> `sourcing-pipeline`.
- "who owns this / what's overdue" -> `slack-task-tracker`.
- "what should I care about today" -> `morning-brief`.
- "add a recurring automation" -> `ernest-use-case-author` (or `ernest new-automation`).

## When Not To Invent

Do not write a new workflow if an installed skill can be configured. Prefer
adding a concern to `memory/standing-concerns.md` (via `ernest new-automation`)
over creating a new skill.
