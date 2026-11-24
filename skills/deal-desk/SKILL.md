---
name: deal-desk
description: Orchestrate the contract workflow from a HubSpot deal through Ironclad — trigger on stage, draft redlines from policy, route legal approval in Slack, and sync status back to CRM. Use when the CEO asks about contracts, MSAs/order forms, redlines, "where's the [account] agreement", or deal-desk status. Pilot-grade and approval-gated: drafting and status reads are fine; creating/sending/signing contracts is manual L3.
version: 1.0.0
---

# Deal Desk (contract workflow)

HubSpot has no native Ironclad link (unlike Salesforce). This skill runs the
**pilot** glue: a deal reaches the right stage → an Ironclad workflow is triggered
via the MATIC connector → redlines handled by Ironclad's AI + Claude drafting from
Notion policy + deal context → legal approvals in Slack/Ironclad → signed contract
and status flow back to HubSpot. Claude can initiate and listen for status via
REST/webhooks.

> Dependencies (be honest about state): MATIC connector wired, Ironclad API access,
> Notion legal policy library, and **legal team sign-off on any AI-drafted redline**.
> If a dependency is missing, report exactly what's needed and stop — do not fake it.

## Inputs

```yaml
deal: ""             # HubSpot deal id or account
trigger_stage: ""    # stage that should kick off the contract workflow
action: "status"     # status | prepare-redline | route-approval
```

## Data sources

- **HubSpot** MCP — deal stage, amount, terms, contacts (status reads).
- **Ironclad** (via MATIC) — workflow state, redlines, approvals, signature status.
- **Notion** MCP — contract policy, fallback positions, approved clause language.
- **Slack** — legal/approver routing and status.
- Export fallback: `data/hubspot/**`, `data/notion/**` (read-only dry run).

## Run sequence

1. **status**: report where each in-flight agreement is (CRM stage ↔ Ironclad state),
   what's blocking, and who owns the next step.
2. **prepare-redline** (draft-only): compare counterpart terms to Notion policy;
   draft suggested redlines with the approved clause + the rationale. Mark every
   deviation from policy. This is a proposal for legal, not a decision.
3. **route-approval**: draft the approval summary (what changed, $ impact, risk)
   for legal in Slack/Ironclad. Routing happens after the CEO/legal approve.
4. On signature, propose the HubSpot status update (draft-first).

## Output

Chat (house format): **Bottom line** (the one agreement needing attention + the
blocker), then a short status list (**deal · stage · blocker · owner**), then
**Read more →** detail. For redlines, summarize deviations from policy first.

## Rules

- **L3 / manual** for anything binding: creating, sending, signing, or committing
  contract terms. Ernest never executes these — it drafts and routes for humans.
- Legal must approve AI-drafted redlines before they leave the building. Flag, don't send.
- Every clause suggestion cites the Notion policy it came from; deviations are called out.
- Money/term changes go to the CEO and legal, never auto-applied to CRM or Ironclad.
- If MATIC/Ironclad/Notion access is missing, state the gap and the setup step — no pretend workflow.
