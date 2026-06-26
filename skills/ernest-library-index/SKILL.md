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
| `read-thread` | (read) | Full thread bodies before watch/draft | read |
| `b2b-lead-grading` | (grade) | Tier inbound B2B (Tier-1/2/Trash) | grade |
| `talent-sourcing-grading` | (grade) | Tier talent, ex-Skolkovo pool | grade |
| `lead-enrichment` | (connector) | Enrich lead/company via Clay + Apollo | read + propose |
| `call-prep` | (connector) | One-pager before a call/meeting | read + draft |
| `call-coaching` | (connector) | Calls → best-practices/coaching library | read + propose |
| `support-triage` | (connector) | Triage Pylon/Zendesk; Fin self-serve | read + draft |
| `hiring-pipeline` | (connector) | Ashby stage tracking + interview prep | read + assign |
| `deal-desk` | (connector) | HubSpot → Ironclad contract workflow (pilot) | status + draft (L3 sign) |
| `ernest-watch` | (orchestration) | Run all concerns | remind |
| `ernest-self-repair` | (meta) | Diagnose + fix/extend Ernest itself | repair |
| `ernest-preferences` | (meta) | Learn + apply CEO's format/autonomy taste | adapt |
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
- Full thread read (email/Slack) → `read-thread` / `ernest read`
- Triage/qualify inbound B2B → `b2b-lead-grading` / `ernest grade --b2b`
- Qualify candidates (ex-Skolkovo) → `talent-sourcing-grading` / `ernest grade --talent`
- "Who is this" / enrich lead or list (Clay/Apollo) → `lead-enrichment`
- Prep for a call/meeting/deal → `call-prep` / `/ernest-call-prep`
- Review calls / build playbook / coaching (Fireflies) → `call-coaching`
- Support load / tickets / self-serve (Pylon/Zendesk/Fin) → `support-triage`
- Hiring status / interview prep / stalled candidates (Ashby) → `hiring-pipeline`
- Contracts / redlines / deal-desk status (Ironclad/MATIC) → `deal-desk` (pilot, L3-gated)
- Something broken / tool missing / "fix it" → `ernest-self-repair` / `/ernest-doctor`
- New automation → `ernest-use-case-author` or `ernest new-automation`
- Change ICP / grading / talent pool → edit `data/grading/*.json` + `memory/icp-*.md`, re-run `ernest grade`
- Clean/shareable view of today, or "answers are messy" → `ernest render --open` (HTML digest); chat answers follow the `CLAUDE.md` house format
- "Too long" / "prefer PDF" / "just do it, don't make me run commands" → `ernest-preferences` (update `memory/preferences.md`, honor it, `ernest feedback`)

Prompts: `docs/examples.md`. Connectors: `docs/connectors.md` (native MCP; no Composio).
