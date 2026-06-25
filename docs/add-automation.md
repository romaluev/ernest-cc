# Add Or Improve Automations (Scaling)

Three ways to grow the system, smallest first.

## 1. Configure an existing playbook (most common)

Every automation is a *concern* in `memory/standing-concerns.md` bound to a
*playbook*. Adding a concern is usually all you need. Use a command, never hand-edited YAML:

```bash
# Add Manoj to a different thread category
ernest new-automation --id add-manoj-to-partnerships \
  --playbook add-collaborator --intent partnerships

# Watch a specific important account
ernest new-automation --id acme-recovery \
  --playbook account-followup-recovery --staleness 5d
```

Available playbooks:

| Playbook | Use it for |
|---|---|
| `account-followup-recovery` | dropped follow-ups; set `priority_tiers` for important-only |
| `inbox-prospect-followup` | inbound prospects matching an intent |
| `add-collaborator` | ensure a teammate is on a thread category |
| `candidate-followup` | candidates in the inbox to assign |
| `list-sync` | reconcile email vs a HubSpot list / sheet |
| `sourcing-pipeline` | track targets to source/contact |
| `task-tracker` | open/overdue tasks by owner |

A new concern is picked up on the next `ernest watch` (or `/ernest-watch`).

## 2. Let Ernest propose one (self-improvement)

Ernest watches for repeated manual work and records candidates. Nothing changes
automatically — you approve by adopting:

```bash
ernest learn                       # see proposals + a ready-to-run adopt command
ernest learn --adopt 1 --id partner-renewals \
  --playbook account-followup-recovery --staleness 7d
```

`--adopt` is the approval step: it registers the concern and scaffolds a skill,
then `ernest watch` puts it to work. Adoption is logged; revert with git.

## 3. Author a brand-new skill

When no playbook fits, use `ernest-use-case-author` (`/ernest-new-automation`).
It interviews you briefly and produces a reviewable proposal: trigger, sources,
output, safety level, dry-run, and rollback. New behavior is never applied
silently.

## Governance

Ernest may propose new concerns, schedules, skills, and memory/config updates.
Ernest may **not** auto-approve external sends, new credentials, new connectors,
legal/money authority, or wider memory access. Every change is reviewable and
reversible (`git revert` or `./install.sh --refresh` to a previous tag).

## Connector-backed use-cases

Some use-cases reach beyond email and need an authorized connector:

- Google Sheet sync (press tracker) — a Sheets MCP, or export the sheet to
  `data/lists/*.csv`.
- HubSpot list sync (Korea/Alvin) — a HubSpot MCP, or export the list to CSV.
- Sourcing new people (ex-Skolkovo operators) — a web/LinkedIn search connector.
- Slack task creation/posting — a Slack MCP.

Until a connector is authorized, the engine runs these against exported files in
`data/` so you can demo and use them offline. Writing back to those systems is
always approval-gated.
