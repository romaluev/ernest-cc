# Examples and Prompts

Copy-paste prompts for Claude Code or plain language. Most work immediately on
sample data after `./install.sh`. Live mail/CRM needs native MCP connectors —
see [connectors.md](connectors.md). Ernest does **not** use Composio.

| Goal | Command |
|---|---|
| Install + first brief | `./install.sh` |
| Daily | `ernest start` |
| Talk to Ernest | open `~/.ernest-cc` in Claude Code |

Most automations are **remind/assign only**. Drafts are optional and never sent
without your approval.

---

## Simple prompts

### Daily overview

```text
What needs me today?
```

```text
/ernest-brief
```

Same as `ernest start`.

---

### Dropped follow-ups

```text
Where did I drop the ball this week?
```

```text
/ernest-watch
```

Card: `dropped-followups`.

---

### Important contacts only

```text
Which VIP or investor contacts am I ignoring?
```

Card: `important-followups` (tier-scoped in config).

---

### Collaborator missing from threads

Flag threads where a teammate should be included but isn't (e.g. B2B intros
you start but don't stay on).

```text
Which partnership threads am I running without my deal lead on them?
```

```text
Make sure [teammate name] is on every B2B intro thread.
```

Card: `b2b-collaborator-coverage`. Action: **add them to the thread**, not draft.

---

### Inbox candidates to assign

```text
Who in my inbox is a strong hire for sales or marketing that we haven't followed up with?
```

```text
Assign candidate follow-ups to the recruiting team.
```

Card: `b2b-candidates`.

---

### Email vs CRM list

Reconcile a regional or segment list (email contacts vs HubSpot export).

```text
Who in my regional email is missing from the CRM list?
```

Card: `korea-list-sync` (name is configurable — any `list-sync` concern).

---

### Email vs spreadsheet

```text
Which press contacts in my email aren't on the tracker sheet yet?
```

Card: `press-list-sync`. Export the sheet to `data/lists/` or connect Sheets MCP.

---

### Sourcing pipeline

```text
Who on our partnership pipeline still needs outreach?
```

```text
Add this LinkedIn profile to the sourcing list: [url]
```

Card: `partnership-sourcing`. Discovering *new* targets needs a search connector;
tracking existing ones works offline.

---

### Open tasks by owner

```text
What company tasks are open or overdue?
```

```text
Who owns the partnership deck and is it late?
```

Card: `slack-task-tracking`.

---

## Drafts (optional)

Only when you want message text prepared. Ernest **never sends**.

```text
draft these
```

```text
/ernest-draft concern=important-followups
```

```text
Prepare draft replies for VIP follow-ups only. Do not send.
```

---

## Workflows (multi-step)

### Monday routine (~5 min)

```text
/ernest-brief
```

If something matters:

```text
Show me collaborator gaps and VIP follow-ups.
```

```text
Assign the top candidate follow-up to recruiting.
```

---

### Fix list drift (email vs CRM)

1. Export the CRM list to `data/lists/` (or connect HubSpot MCP).
2. Tag matching mail threads with the right `category` in exports.
3. Run `ernest start` or `/ernest-watch`.
4. Ask:

```text
List email contacts missing from the CRM list. No writes.
```

HubSpot writes stay approval-gated.

---

### Fix sheet drift (email vs tracker)

1. Export the Google Sheet to `data/lists/press-sheet.csv` (or connect Sheets MCP).
2. Run `ernest start`.
3. Ask:

```text
Sync my press inbox against the tracker sheet. Gaps only.
```

---

### Add a recurring check

**Claude:**

```text
/ernest-new-automation
Every Friday, flag investor follow-ups I owe. Remind only.
```

**Terminal:**

```bash
ernest new-automation --id investor-followups \
  --playbook account-followup-recovery --staleness 5d
ernest start
```

See [add-automation.md](add-automation.md).

---

### Self-improvement

When you repeat something manually:

```text
I keep checking partner renewals every Monday. Ernest should watch that.
```

```bash
ernest learn
ernest learn --adopt 1 --id partner-renewals \
  --playbook account-followup-recovery --staleness 7d
ernest start
```

Nothing applies until you run `--adopt` or approve in Claude.

---

### Onboard (once, optional)

```text
/ernest-onboard
```

Personalizes memory and walks through connecting Gmail/HubSpot via native MCP.
Not required for `ernest start` on sample or exported data.

---

## Live data (needs native MCP)

Ernest still won't send or write without approval.

```text
Search my mail for threads with [account name] in the last 90 days. Cross-check HubSpot tier. Remind only.
```

```text
Find B2B threads from the last 30 days where I'm the only internal participant. Flag missing collaborators.
```

```text
Read #partnerships in Slack for open asks this week. Show owners and due dates.
```

```text
Compare my press inbox to the tracker sheet. Propose rows to add — don't write yet.
```

```text
Find similar profiles on LinkedIn for partnership outreach. Add top candidates to the pipeline as proposals only.
```

---

## Card reference

| Card id | What it catches |
|---|---|
| `dropped-followups` | Threads you owe a reply on |
| `important-followups` | VIP/investor-tier slips |
| `inbox-prospects` | Inbound prospects waiting |
| `b2b-collaborator-coverage` | Threads missing a designated teammate |
| `b2b-candidates` | Hire candidates needing assignment |
| `korea-list-sync` | Email vs CRM list gaps (any region/segment) |
| `press-list-sync` | Email vs sheet gaps |
| `partnership-sourcing` | Pipeline targets not yet contacted |
| `slack-task-tracking` | Open/overdue tasks by owner |

Cards: `~/ErnestVault/Ernest/00-Watch/` after `ernest start`.

---

## Demo (no install)

```bash
./scripts/demo.sh
```

Full lifecycle on bundled sample data.
