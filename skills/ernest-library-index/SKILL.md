---
name: ernest-library-index
description: Catalog of installed use-cases. Check before inventing new workflows.
version: 1.0.0
---

# Ernest Library Index

| Skill | Playbook | Purpose | Mode |
|---|---|---|---|
| `morning-brief` | (brief) | Today's open loops | remind |
| `account-followup-recovery` | `account-followup-recovery` | Dropped follow-ups; VIP tier filter | watch + draft |
| `mail-deep-audit` | `account-followup-recovery` | Full-window owed-reply sweep (chunked) | watch + draft |
| `inbox-prospect-followup` | `inbox-prospect-followup` | Inbound prospects | watch + draft |
| `add-collaborator` | `add-collaborator` | Teammate missing from threads | assign |
| `candidate-followup` | `candidate-followup` | Inbox candidates → assign owners | assign |
| `list-sync` | `list-sync` | Email vs CRM or sheet | assign |
| `sourcing-pipeline` | `sourcing-pipeline` | Pipeline targets to contact | assign |
| `slack-task-tracker` | `task-tracker` | Open/overdue tasks by owner | assign |
| `ernest-watch` | (orchestration) | Run all concerns | remind |
| `ernest-use-case-author` | (meta) | Propose new automations | proposal |

## Routing

- Slipped follow-ups → `account-followup-recovery`
- Full year / back-catalog owed replies → `mail-deep-audit` / `/ernest-audit`
- VIP-only → `important-followups` concern (tier params)
- Missing collaborator on threads → `add-collaborator`
- Inbox candidates → `candidate-followup`
- Email vs list → `list-sync`
- Sourcing list → `sourcing-pipeline`
- Task ownership → `slack-task-tracker`
- Daily overview → `morning-brief` / `ernest start`
- New automation → `ernest-use-case-author` or `ernest new-automation`

Prompts: `docs/examples.md`. Connectors: `docs/connectors.md` (native MCP; no Composio).
