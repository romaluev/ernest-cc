# Examples and Prompts

Copy-paste prompts for Claude Code or plain language. Most work immediately on
sample data after `./install.sh`. Live mail/CRM needs native MCP connectors —
see [connectors.md](connectors.md). Ernest does **not** use Composio.

| Goal | Command |
|---|---|
| Install + first brief | `./install.sh` |
| Daily | `ernest start` |
| Read full threads | `ernest read --owed` |
| Grade inbound + talent | `ernest grade` |
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

### Read full threads (email, Slack, etc.)

Ernest needs **message bodies**, not search snippets, before watch or draft.

```bash
ernest read --owed
ernest read --thread slack-partnership-deck
```

```text
/ernest-read

Read the full Slack thread for the partnership deck and tell me what I owe Jordan.
```

```text
Read the full email thread with [contact] before you draft — every message.
```

Cached threads: `~/ErnestVault/Ernest/00-Threads/`.  
`ernest start` auto-reads owed threads from exports.

---

### Grade inbound B2B (Tier-1 / Tier-2 / Trash)

Sort inbound so you only personally handle what matters. Criteria live in
`memory/icp-b2b.md` (AI studios + ad agencies are core ICP).

```bash
ernest grade --b2b
```

```text
/ernest-grade

Triage my inbox. Who's Tier-1 (Fortune 500, agencies, AI studios, enterprise-now,
big funds, prior contact with me)? Drop the trash. Don't reply yet.
```

Card: `b2b-grades--<date>.md`, sorted Tier-1 first with reasons + flags.

---

### Grade talent (ex-Skolkovo pool)

Criteria live in `memory/icp-talent.md`.

```bash
ernest grade --talent
```

```text
/ernest-grade

Grade my ex-Skolkovo sourcing list. Tier-1 only if Big Tech senior, strong
technical base, or AI-media product experience — and likely interested, not a
current Higgsfield investor/employee.
```

Card: `talent-grades--<date>.md`.

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

### Full-year owed-reply audit

Daily watch only looks at recent slips (`staleness: 7d`). A **back-catalog audit**
needs an explicit window and chunked mail search — otherwise live MCP stops after
the first recent page.

**Terminal first** (writes a chunk manifest Ernest must finish):

```bash
ernest audit --window 365d
```

**Then in Claude:**

```text
/ernest-audit

Audit every thread I owe a reply on in the last 365 days. Process every date
chunk in the manifest before you summarize. Exclude newsletters, job-seeker
intros, and cold vendor outreach. Remind only — no drafts.
```

Shorter plain language:

```text
Full year audit: every email where they wrote last and I never replied. Finish
the whole year before you report. Don't stop at this week.
```

Card: `mail-audit--<date>.md` in `00-Watch/`.

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

### Fix something / add a missing tool

Ernest repairs and extends itself — you shouldn't have to debug it.

```bash
ernest doctor
```

```text
/ernest-doctor

Something's off and I can't read my Slack. Figure out what's missing, find the
right connector, and set it up — ask me before anything that needs my login.
```

---

### Change the ICP or talent criteria (flexible)

ex-Skolkovo is just the current talent plan. Criteria are living config.

```text
Change our talent focus from ex-Skolkovo to ex-FAANG design leads, then re-grade.
```

```text
Add "Series C+ fintechs" as a Tier-1 B2B signal and re-sort my inbox.
```

Edits land in `data/grading/*.json`; then `ernest grade` re-runs.

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
| `b2b-grades` | Inbound B2B sorted Tier-1 / Tier-2 / Trash (`ernest grade`) |
| `talent-grades` | ex-Skolkovo talent sorted Tier-1 / 2 / 3 (`ernest grade --talent`) |
| `dropped-followups` | Threads you owe a reply on (recent; daily watch) |
| `mail-audit` | Full-window owed-reply sweep (on-demand; use `ernest audit`) |
| `important-followups` | VIP/investor-tier slips |
| `inbox-prospects` | Inbound prospects waiting |
| `b2b-collaborator-coverage` | Threads missing a designated teammate |
| `b2b-candidates` | Hire candidates needing assignment |
| `korea-list-sync` | Email vs CRM list gaps (any region/segment) |
| `press-list-sync` | Email vs sheet gaps |
| `partnership-sourcing` | Pipeline targets not yet contacted |
| `slack-open-threads` | Slack threads you owe a reply on |
| `slack-task-tracking` | Open/overdue tasks by owner |

Cards: `~/ErnestVault/Ernest/00-Watch/` after `ernest start`.

---

## Demo (no install)

```bash
./scripts/demo.sh
```

Full lifecycle on bundled sample data.
