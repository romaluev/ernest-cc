---
name: support-triage
description: Triage inbound support, route it, draft replies, and surface self-serve deflection. Use when the CEO/team asks about support load, tickets, escalations, "what's on fire in support", response-time risk, or wants a self-serve/deflection view. Reads tickets; all replies and status changes are draft-first.
version: 1.0.0
---

# Support Triage

Higgsfield runs support on Pylon + Zendesk and is piloting Intercom Fin for
self-serve. There is no self-serve routing flow yet — this skill triages load,
proposes routes, and flags what Fin could deflect.

## Inputs

```yaml
scope: "open"        # open | breaching-sla | escalations | last_24h
queue: "*"           # Pylon, Zendesk, or all
```

## Data sources (read-only; swappable)

- **Pylon** + **Zendesk** MCP — tickets: status, priority, age, SLA, requester, last reply.
- **Intercom (Fin)** MCP — what Fin already resolved / could deflect (when connected).
- **Slack** — support "front door" threads needing a human.
- **Notion** — help/policy docs used to answer or to spot doc gaps.
- Export fallback: `data/support/**`, `data/slack/**`.

## Run sequence

1. Pull tickets in `scope`; rank by SLA risk, customer tier, and blast radius.
2. Group into: needs-human-now, routeable (assign owner/queue), and
   **self-serve candidates** (repetitive how-to → Fin/docs deflection).
3. For human-needed tickets, draft replies grounded in Notion docs — **draft-first**.
4. Flag recurring questions as doc/Fin gaps (the real fix is deflection, not faster typing).
5. Propose assignments; never reassign or change status without approval.

## Output

Chat (house format): **Bottom line** (biggest SLA/customer risk right now),
then a short triage list (**who · action · why now · ticket link**), then
**Read more →** the full queue view. Separate "needs you" from "routeable" from
"self-serve candidate".

## Rules

- Read-only on tickets. Replies, reassignments, status/SLA changes are proposals for approval.
- Customer-facing drafts must cite the doc/policy they're based on; no invented commitments.
- Prefer deflection: every repeated question is a Fin/Notion gap to close, logged for follow-up.
- Escalate anything legal, security, refund, or churn-risk to the CEO rather than auto-answering.
