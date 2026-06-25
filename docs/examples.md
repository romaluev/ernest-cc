# Examples and Prompts

Copy-paste prompts for the CEO. Most need **no setup beyond `./install.sh`** —
they work on sample data immediately, and on live Gmail/HubSpot/Slack once
accounts are connected.

## Before you read this

| You want | Do this |
|---|---|
| Install + see value now | `./install.sh` |
| Every morning | `ernest start` |
| Talk to Ernest in Claude | open `~/.ernest-cc`, say any prompt below |

Everything below is **optional**. If a prompt mentions drafts, ignore it — most
automations are remind/assign only.

---

## Simple — one sentence

### Daily

```text
What needs me today?
```

```text
/ernest-brief
```

Same as `ernest start`. Ernest lists follow-ups, assignments, and sync gaps.

---

### Dropped follow-ups

```text
Where did I drop the ball this week?
```

```text
/ernest-watch
```

Surfaces threads you owe a reply on. Card: `dropped-followups`.

---

### Important accounts only (Nubank-style)

```text
Which important contacts am I ignoring?
```

Uses the `important-followups` concern (VIP/investor tier). No extra setup.

---

### Add Manoj to B2B threads

```text
Which B2B intros am I running without Manoj?
```

```text
Make sure Manoj is on every B2B thread so my intros don't get dropped.
```

Card: `add-manoj-to-b2b`. Action is **assign** (add him to the thread), not draft.

---

### Candidates for Alua / Limon

```text
Who in my inbox is a good B2B marketing or sales candidate that we haven't followed up with?
```

```text
Assign candidate follow-ups to Alua and Limon.
```

Card: `b2b-candidates`.

---

### Korea list sync (Alvin / HubSpot)

```text
Who in my Korea email is missing from Alvin's HubSpot list?
```

Card: `korea-list-sync`. Offline: compares email vs `data/lists/korea-hubspot.csv`.
Live: needs HubSpot MCP or an exported list in `data/lists/`.

---

### Press list sync (TechCrunch / sheet)

```text
Which press contacts in my email aren't on the press tracker sheet yet?
```

```text
Is Rebecca at TechCrunch on our press list?
```

Card: `press-list-sync`. Export the Google Sheet to CSV in `data/lists/` or
connect a Sheets MCP.

---

### Sourcing (partnership / hire)

```text
Who on our sourcing list still needs outreach?
```

```text
Add https://www.linkedin.com/in/anda-gansca to the partnership pipeline.
```

Card: `partnership-sourcing`. Finding *new* people like ex-Skolkovo operators
needs a search connector; tracking who to contact works offline now.

---

### Slack tasks (overdue by owner)

```text
What company tasks are open or overdue?
```

```text
Who owns the BridgeAI deck and is it late?
```

Card: `slack-task-tracking`. First step toward transparent task tracking from Slack.

---

## Simple — when you want drafts (optional)

Only if you explicitly want message text prepared. Ernest **never sends**.

```text
draft these
```

```text
/ernest-draft concern=dropped-followups
```

```text
Prepare draft replies for the Nubank thread only. Do not send.
```

---

## Complex — multi-step workflows

### 1. Monday morning (5 minutes)

```text
/ernest-brief
```

Then, only if something matters:

```text
Show me the add-manoj card and the important follow-ups card.
```

```text
Assign the Dana Kim candidate reach-out to Alua.
```

No drafts unless you ask.

---

### 2. Fix Korea email vs HubSpot drift

**Goal:** email Korea contacts stay in sync with Alvin's HubSpot list.

1. Export Alvin's list to CSV → `data/lists/korea-hubspot.csv` (or connect HubSpot).
2. Tag Korea threads in mail exports with `category: korea` (or let live mail MCP handle it).
3. Run:

```text
/ernest-watch
```

4. For each gap Ernest flags:

```text
Add SeoulTech to Alvin's Korea list — show me what's missing first.
```

Writing to HubSpot stays approval-gated.

---

### 3. Press tracker vs inbox

**Goal:** Rebecca / TechCrunch and other press contacts match the sheet.

1. Export the [press tracker sheet](https://docs.google.com/spreadsheets/d/1mtj9eKH5bpmoKwbKM0ujLZqlttdLcSkNHRn13qWS6eg/edit?gid=1814998301#gid=1814998301) to `data/lists/press-sheet.csv`.
2. Run `ernest start` or `/ernest-watch`.
3. Ask:

```text
Sync my press email against the tracker sheet. List gaps only, no writes.
```

---

### 4. Scale: add a new recurring check

**In Claude:**

```text
/ernest-new-automation
```

```text
Every Friday, check investor follow-ups and tell me who I owe. Remind only, no drafts.
```

**In terminal (same outcome):**

```bash
ernest new-automation --id investor-followups \
  --playbook account-followup-recovery --staleness 5d
ernest start
```

---

### 5. Self-improvement (Ernest learns a pattern you repeat)

When you catch yourself doing something manually every week:

```text
I keep manually checking partner renewals every Monday. Ernest should watch that.
```

Then:

```bash
ernest learn
ernest learn --adopt 1 --id partner-renewals \
  --playbook account-followup-recovery --staleness 7d
ernest start
```

Or in Claude: `/ernest-learn` and approve the proposal. Nothing applies until you adopt.

---

### 6. Onboard Ernest to you (once)

```text
/ernest-onboard
```

Or:

```bash
ernest onboard
```

Answer: name, company, what you want off your plate, mail provider, HubSpot.
Then connect Gmail/HubSpot when prompted. After that, `ernest start` every day.

---

## Complex — Claude-only (needs connectors)

These need live Gmail / HubSpot / Slack / Sheets. Ernest still won't send or write without approval.

```text
Search my mail for all threads with Nubank in the last 90 days. Cross-check HubSpot tier and last touch. Remind only.
```

```text
Find B2B partnership threads from the last 30 days where I'm the only internal participant. Flag ones missing Manoj.
```

```text
Read #partnerships in Slack for open asks from this week and add them to task tracking. Show owners and due dates.
```

```text
Compare my press inbox to the Google Sheet press list. Propose rows to add — don't write to the sheet yet.
```

```text
Find people on LinkedIn similar to ex-Skolkovo founders in the US. Add the best 5 to the sourcing pipeline as proposals only.
```

---

## What each card means (quick map)

| Card id | Your words |
|---|---|
| `add-manoj-to-b2b` | "Add Manoj to B2B threads" |
| `b2b-candidates` | "Alua/Limon reach out to candidates" |
| `important-followups` | "Nubank / VIP follow-ups I owe" |
| `korea-list-sync` | "South Korea email vs Alvin's HubSpot list" |
| `press-list-sync` | "Press list vs the tracker sheet" |
| `partnership-sourcing` | "Source more partnership/hire contacts" |
| `slack-task-tracking` | "Transparent tasks from Slack" |
| `dropped-followups` | "General dropped follow-ups" |
| `inbox-prospects` | "Inbound prospects waiting" |

Cards live in `~/ErnestVault/Ernest/00-Watch/` after `ernest start`.

---

## Demo without your real email

From the repo (no install):

```bash
./scripts/demo.sh
```

Runs the full lifecycle on sample data: all use-case cards, brief, scale, and self-improve.
