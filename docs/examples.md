# Prompts that work

Talk to Ernest in plain English — paste any of these. They're written to produce a
great result on the first try: each says the **goal**, the **constraints**, and the
**output** you want. Ernest is **draft-first** — it prepares, you approve every send.

Works on the bundled sample data right after install. Live mail/CRM/Slack needs
native MCP connectors ([connectors.md](connectors.md)) — Ernest does **not** use
Composio. Each prompt notes the card it writes (in `~/ErnestVault/Ernest/00-Watch/`)
or the equivalent command.

---

## Start here

**Your morning, in one ask** — `ernest start` / `/ernest-brief`
```text
Give me my morning brief. Bottom line first, then up to 6 things that actually
need me today — for each: who, the one action, why it's urgent, and the source.
Open loops, slipping follow-ups, VIPs gone quiet, stalled deals, calendar
conflicts. Skip anything that can wait. Don't draft or send anything yet.
```

**Make answers short and on-your-terms** — Ernest leads with a **Bottom line**, a
few bullets, then a "Read more →" link to a clean digest (`ernest render`). Teach it
once and it remembers (saved to `memory/preferences.md`; log with `ernest feedback`):
```text
From now on: keep chat answers to 4 bullets max, link the rest, prefer a PDF I can
forward, and never show me trash-tier leads. Confirm you've saved that.
```

---

## Triage & follow-ups

**What did I drop?** — `/ernest-watch` → card `dropped-followups`
```text
Where did I drop the ball? Show every thread where someone is waiting on ME,
oldest first, with who/what/how-many-days. Group by how costly it is to keep them
waiting. Remind only — no drafts.
```

**VIPs and investors I'm ignoring** — card `important-followups`
```text
Which VIP, investor, or top-client contacts have gone quiet on my side for 10+
days? Rank by relationship value. For each, one line on the last exchange and the
nudge I should send. Don't write the messages yet.
```

**Full-year owed-reply audit** — `ernest audit --window 365d`, then `/ernest-audit`
```text
Audit every thread I owe a reply on in the last 365 days. Process every date chunk
in the manifest before you summarize — Don't stop at this week. Exclude newsletters,
job-seeker intros, and cold vendor pitches. Remind only. Card: mail-audit.
```

**Read the whole thread before acting** — `ernest read` / `/ernest-read` → `slack-open-threads`
```text
Read the FULL history of my thread with [contact] — every message, email and Slack,
not snippets. Then tell me exactly what I owe them and the cleanest way to close it.
```

---

## Inbound & sales

**Triage inbound, ranked** — `ernest grade` / `/ernest-grade` → card `b2b-grades`
```text
Triage my inbox as B2B leads. Tier-1 = real enterprise buyers, agencies, AI studios,
market leaders, big funds, or anyone with prior contact or clear buying intent.
Drop obvious cold/SEO/vendor spam. Rank each tier by match strength, give one-line
reasons, and flag anything you're unsure about. Don't reply — just sort.
```

**Don't run B2B threads solo** — card `b2b-collaborator-coverage`
```text
Find B2B/partnership threads where I'm the only person from our side. For each, say
who should be looped in and add them to the thread (don't draft a message).
```

**Enrich then grade a lead** — skill `lead-enrichment`
```text
Who is this lead: [name/email/url]? Enrich with role, company size, funding, and
recent signals, then grade them Tier-1/2/trash against our ICP. Propose CRM updates
as a reviewable batch — don't write to the CRM.
```

**Deal desk** — skill `deal-desk` (contracts/signing stay manual, L3)
```text
Where's the [account] agreement? Show CRM stage vs contract status and the current
blocker. Draft suggested redlines from our policy doc. Legal approves before
anything moves — nothing sent or signed.
```

---

## Hiring & sourcing

**Source wide, then rank** — `/ernest-grade` (talent) → card `talent-grades`
```text
Source senior gen-AI / video talent for our ex-NovaLabs focus pool. Cast a WIDE
net: include adjacent titles (research scientist, ML lead, founding engineer) and
peer companies, pull 30-50 candidates, THEN rank by fit. Tier-1 = senior at a top
lab, strong technical base, or AI-media product depth — and likely interested, not
a current employee/investor. Shortlist the top 8 with reasons. Don't message anyone.
```

**Inbox hires to route** — card `b2b-candidates`
```text
Who in my inbox is a strong hire for sales/marketing/eng that we haven't followed
up with? Assign each to the right owner on the recruiting team — draft only.
```

**Sourcing pipeline** — card `partnership-sourcing`
```text
Who on our partnership/sourcing pipeline still needs a first outreach? Sort by
priority. Add this profile to the list: [url]. Discovering NEW targets needs a
search connector; tracking existing ones works offline.
```

**Interview prep & pipeline hygiene** — skill `hiring-pipeline`
```text
Who's stuck in the hiring pipeline or waiting on us? Prep me for this week's
interviews against the role rubric, and nudge owners for missing scorecards —
draft the nudges, don't send.
```

---

## Calls, support, CRM

**Be call-ready in 5 minutes** — `/ernest-call-prep [account]` → skill `call-prep`
```text
I have a call with [account] at 3pm. Pull the thread + CRM + last meeting notes and
give me a one-pager: where we left off, who's on it, 5 discovery questions, the top
risk, and the next step to lock. Mark what's from CRM vs the web.
```

**Turn calls into a playbook** — skill `call-coaching`
```text
Review last week's calls. What objections came up and which responses actually
moved the deal? Turn the wins into 5 reusable plays. Don't post anything.
```

**What's on fire in support?** — skill `support-triage`
```text
Triage support right now: separate needs-a-human from routeable from self-serve.
Rank by risk (churn/severity), suggest an owner for each, and draft replies for the
top 3 — don't send.
```

**Reconcile a list (email vs CRM)** — card `korea-list-sync`
```text
Compare my [region/segment] email contacts against the CRM list and show who's
missing from the CRM. Propose additions as a reviewable batch — no writes.
```

**Reconcile a sheet (email vs tracker)** — card `press-list-sync`
```text
Which press contacts in my inbox aren't on the tracker sheet yet? List the rows to
add — don't write to the sheet.
```

**Open tasks by owner** — card `slack-task-tracking`
```text
What company tasks are open or overdue, by owner? Flag anything past due and who's
blocking it.
```

---

## Drafts (only when you ask)

Ernest never sends. To get message text prepared, reply **`draft these`** to any
reminder card, or:
```text
draft these — VIP follow-ups only. In my voice, short, warm, with a clear next
step. Show them to me for approval; send nothing.
```
Command form: `/ernest-draft concern=important-followups`.

---

## Power moves (multi-step — paste and let it run)

**Run my whole Monday**
```text
Run my Monday: triage everything waiting on me, rank what actually matters, read the
full history on the top 5, and draft replies for them in my voice. Tell me who to
loop in on each. I'll review and approve sends. ~10 minutes, one report at the end.
```

**Save the quiet accounts**
```text
Find every important client that's gone quiet for 2+ weeks. Read each thread's full
history, draft a warm, specific re-open for each (reference the real last topic, not
a template), and rank by revenue at risk. Nothing sent.
```

**Inbound → pipeline, end to end**
```text
Take this week's inbound: grade Tier-1/2/trash, ignore trash, for each Tier-1 draft
a first reply AND tell me who internally should own it. Propose the CRM updates.
Approvals before any send or write.
```

**Weekly cleanup**
```text
Preview the messy CRM records and fix only the obviously-mechanical ones (names,
company, title). Draft the list-sync gaps between my email and the CRM. Summarize
what changed and what's waiting on me. Don't apply anything risky.
```

---

## Make it recurring / let it improve

**Add a recurring check** — `/ernest-new-automation`
```text
/ernest-new-automation
Every Friday at 5pm, flag investor follow-ups I owe and partner renewals coming up
in 30 days. Remind only.
```
Terminal: `ernest new-automation --id investor-followups --playbook account-followup-recovery --staleness 5d`

**Let Ernest propose its own automations** — `ernest learn`
```text
I keep manually checking partner renewals every Monday. You should watch that for me.
```
Then review and adopt: `ernest learn` → `ernest learn --adopt 1 --id partner-renewals --playbook account-followup-recovery`. Nothing applies until you approve.

**Change the ICP / talent focus (living config)**
```text
Change our talent focus from ex-NovaLabs to ex-FAANG design leads and re-grade. Also
add "Series C+ fintechs" as a Tier-1 B2B signal and re-sort my inbox.
```

**Fix something / connect a missing tool** — `ernest doctor` / `/ernest-doctor`
```text
/ernest-doctor
Something's off and I can't read my Slack. Find what's missing, set up the right
connector, and verify it — ask me before anything that needs my login.
```

---

## Live data (needs native MCP connectors)

Still draft-first — nothing sends or writes without approval.
```text
Search my mail for threads with [account] in the last 90 days, cross-check the CRM
tier, and tell me which need me this week. Remind only.
```
```text
Read #partnerships in Slack for open asks this week. Show owners and due dates, and
who I owe a reply. Card: slack-open-threads.
```

---

## Card reference

Cards land in `~/ErnestVault/Ernest/00-Watch/` after `ernest start`.

| Card id | What it catches |
|---|---|
| `b2b-grades` | Inbound B2B sorted Tier-1/2/Trash, ranked by match score |
| `talent-grades` | ex-NovaLabs talent sorted Tier-1/2/3, ranked by fit |
| `dropped-followups` | Threads you owe a reply on (recent) |
| `mail-audit` | Full-window owed-reply sweep (`ernest audit`) |
| `important-followups` | VIP/investor-tier slips |
| `b2b-collaborator-coverage` | Threads missing a teammate |
| `b2b-candidates` | Hire candidates needing assignment |
| `korea-list-sync` | Email vs CRM list gaps (any region/segment) |
| `press-list-sync` | Email vs tracker-sheet gaps |
| `partnership-sourcing` | Pipeline targets not yet contacted |
| `slack-open-threads` | Slack threads you owe a reply on |
| `slack-task-tracking` | Open/overdue tasks by owner |

---

## Try it now (no install)

```bash
./scripts/demo.sh
```
Runs the full lifecycle on bundled sample data so you can see real output first.
