---
name: ernest-library-index
description: Use before inventing or adding workflows. Lists Ernest's installed use-cases, their purpose, safety level, and when not to use them.
version: 1.0.0
---

# Ernest Library Index

Use this catalog before choosing or creating a workflow.

## Installed Use-Cases

| Skill | Category | What It Does | Default Mode |
|---|---|---|---|
| `morning-brief` | brief | Summarizes today's open loops from watch cards, inbox/calendar, and HubSpot | remind-only |
| `account-followup-recovery` | follow-up | Finds stalled account threads, quiet deals, and unmet promises; drafts recoveries on ask | watch + draft |
| `inbox-prospect-followup` | inbox | Finds inbound/prospect threads matching a profile and no follow-up; drafts replies on ask | watch + draft |
| `ernest-watch` | orchestration | Runs standing concerns and writes reminder cards | remind-only |
| `ernest-use-case-author` | self-improvement | Adds or improves automations through reviewable proposals | proposal-only |

## Selection Rules

- If the CEO asks "what slipped", use `account-followup-recovery`.
- If the CEO asks "who in my inbox matches X", use `inbox-prospect-followup`.
- If the CEO asks "what should I care about today", use `morning-brief`.
- If the CEO asks to add a recurring automation, use `ernest-use-case-author`.

## When Not To Invent

Do not write a new workflow if an installed skill can be configured. Prefer updating `memory/standing-concerns.md` with a new concern over creating a new skill.
