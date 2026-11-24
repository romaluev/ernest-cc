---
name: hiring-pipeline
description: Keep the hiring pipeline moving — stalled candidates, interview prep, scorecard chasing, and offer follow-ups. Use when the CEO asks about hiring status, candidates waiting on us, interview prep, "who's stuck in the pipeline", or onboarding handoffs. Reads ATS; all candidate-facing messages and stage changes are draft-first.
version: 1.0.0
---

# Hiring Pipeline

Northwind runs the ATS in Ashby with no automation yet. This skill adds the
remind/assign layer so candidates don't stall and interviewers stay prepared.
It complements `talent-sourcing-grading` (who to pursue) and `candidate-followup`.

## Inputs

```yaml
scope: "active"      # active | stalled | onsite-this-week | offers-out
role: "*"            # optional: a specific req
staleness: "3d"      # candidate waiting on us beyond this = surfaced
```

## Data sources (read-only; swappable)

- **Ashby** MCP — candidates, stages, interviews, scorecards, who owes what.
- **Google Calendar** — upcoming interviews needing prep / panel readiness.
- **Gmail / Slack** — candidate comms and internal hiring threads.
- **Notion** — interview rubrics, role scorecards, hiring bar.
- Export fallback: `data/ashby/**`, `data/calendar/**`.

## Run sequence

1. Pull candidates in `scope`; find anyone waiting on us past `staleness`,
   missing scorecards, or with an unscheduled next step.
2. For interviews this week, assemble prep: candidate summary, role rubric,
   what each interviewer should probe (from Notion).
3. Surface offer/decision bottlenecks and onboarding handoffs.
4. Propose actions: nudge interviewer for scorecard, schedule next round,
   draft a candidate update — **draft-first**, assign owners; no ATS writes.

## Output

Chat (house format): **Bottom line** (the candidate/decision most at risk of
being lost), then a short list (**candidate · stage · action · why now**), then
**Read more →** full pipeline view. For interviews, link the prep doc.

## Rules

- Read-only on the ATS. Stage moves, scheduling, and candidate messages are proposals for approval.
- Protect candidate experience: surface anyone waiting too long before they go cold.
- Use the role rubric for prep; don't invent bar/criteria. Flag bias-risk language for review.
- Never share compensation or internal debrief notes outside the hiring panel.
