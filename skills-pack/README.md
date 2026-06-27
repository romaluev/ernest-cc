# Ernest skills pack — the manual set

Seven Claude **skills** that cover the operating-layer work the CEO asked for, as a
shareable, self-contained folder. Use these **without Hermes, without the VPS, and
without the plugin** — just drop them into Claude and talk to it. (If you also have
the Ernest engine installed, the `ernest …` commands inside a few skills are an
optional accelerator; if you don't, ignore them — Claude does the same work directly
through your connected tools.)

All of these are **draft-first**: they watch, find, rank, and *prepare* — they never
send, post, or write to a live system without your explicit approval.

## What's in the pack (mapped to the asks)

| Skill | Covers the ask | What it does |
|---|---|---|
| **account-followup-recovery** | "Nubank follow up — find every important contact where the follow-up was dropped" | Finds genuinely-dropped follow-ups by searching **all** your tools (mail, HubSpot, Slack, calendar) and **cross-checking** each one for whether it was already handled elsewhere (so it never flags something you already closed). First sweep covers 12 months, then incremental. |
| **add-collaborator** | "Add Manoj to all B2B threads" (your intros slip; Manoj's don't) | Flags B2B/partnership threads where the right teammate isn't included, and adds them — so intros stop falling through you. |
| **candidate-followup** | "Alua / Limon reach out — find good B2B marketing/sales candidates in my email and follow up" | Finds candidate threads in your inbox, ranks them, and prepares follow-ups for review. |
| **list-sync** | "South Korea — sync my email with Alvin's HubSpot list" · "Press list (TechCrunch/Rebecca) — sync with the Google Sheet" | Reconciles an email/segment against a CRM list or a spreadsheet and proposes what's missing on each side — no writes until you approve. |
| **sourcing-pipeline** | "Find a way to source more partnership/hire contacts (e.g. ex-Skolkovo in the USA)" | Tracks and surfaces sourcing targets that still need outreach; add a profile by URL. |
| **talent-sourcing-grading** | grading the people you source (the ex-Skolkovo pool) | Casts a **wide net**, then ranks candidates by a fit **score** (Tier-1/2/3) so the strongest surface first. Pool + criteria are editable config. |
| **slack-task-tracker** | "Transparent task tracking from Slack across the company" | Pulls open/overdue tasks and asks out of Slack, by owner, so work in threads doesn't get lost. |

## How to use it (manual, no setup)

1. **Drop the skills in.** Copy the seven folders into your Claude skills directory —
   `~/.claude/skills/` (global) or a project's `.claude/skills/` — or load this folder
   in Cowork. (Each folder has a `SKILL.md`; some have a `references/` subfolder.)
2. **Connect your tools** in Claude as you normally would (Gmail/Outlook, HubSpot,
   Slack, Calendar). The skills use whatever's connected.
3. **Just ask**, in plain words:
   - "Who did I drop the ball with? Search everywhere and skip anything already handled."
   - "Make sure Manoj is on every B2B intro thread."
   - "Find B2B sales/marketing candidates in my inbox and draft follow-ups."
   - "Sync my Korea contacts against Alvin's HubSpot list — what's missing?"
   - "Source more ex-Skolkovo people in the US and rank them."

## Idempotent + safe to re-run

Re-running any of these is safe. They **propose and draft**; they don't auto-act, so
nothing duplicates. The one skill that does a live action — `add-collaborator` (adding
a teammate to a thread) — is naturally idempotent (adding someone already on the
thread is a no-op) and still asks before it acts. Nothing is ever sent or written to a
live system without your approval.

## The improvements baked in (vs. a naive version)

- **Search wide, then cross-check for resolution.** A thread that looks dropped in mail
  may already be resolved in Slack or closed in HubSpot — these skills check the *other*
  tools first and suppress anything already handled (and propose a CRM update if the
  record is stale).
- **Score-ranked results.** Leads and candidates are ranked by match strength, not just
  date, so the best ones lead.
- **Cold-start window.** The first follow-up sweep looks back 12 months; later sweeps are
  incremental, so repeats are fast.
