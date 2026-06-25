# Add or Scale Automations

Three paths, smallest first. Prompt examples: [examples.md](examples.md).

## 1. Configure an existing playbook

Most new behavior is a **concern** (trigger + parameters), not a new skill:

```bash
ernest new-automation --id regional-crm-sync \
  --playbook list-sync --staleness 7d
```

```bash
ernest new-automation --id b2b-deal-lead \
  --playbook add-collaborator
```

| Playbook | Use for |
|---|---|
| `account-followup-recovery` | Stalled threads; add `priority_tiers` for VIP-only |
| `inbox-prospect-followup` | Inbound leads by intent |
| `add-collaborator` | Teammate missing from thread category |
| `candidate-followup` | Inbox candidates → assign owners |
| `list-sync` | Email vs CRM list or sheet |
| `sourcing-pipeline` | Targets to source/contact |
| `task-tracker` | Open/overdue tasks |

Next `ernest start` picks it up.

## 2. Self-improvement (propose → approve)

```bash
ernest learn                              # see proposals
ernest learn --adopt 1 --id my-check \
  --playbook account-followup-recovery --staleness 7d
ernest start
```

Nothing changes until `--adopt` or explicit CEO approval in Claude.

## 3. New skill (when no playbook fits)

`/ernest-new-automation` in Claude — produces a reviewable proposal with
trigger, sources, safety level, dry-run, and rollback. Never applied silently.

## Connectors for live data

| Need | Offline | Live |
|---|---|---|
| Mail | `data/mail/` | Gmail/Outlook MCP |
| CRM | `data/hubspot/` | HubSpot MCP |
| Sheet | `data/lists/*.csv` | Sheets MCP |
| Slack tasks | `data/slack/tasks.csv` | Slack MCP |
| New sourcing | manual CSV | search MCP |

No Composio. See [connectors.md](connectors.md).

## Governance

Ernest may propose concerns, schedules, and skills. Ernest may **not** auto-approve
sends, credentials, new connectors, or legal/money authority. Revert via git or
`./install.sh --refresh` to a prior version.
