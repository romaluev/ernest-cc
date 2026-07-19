---
name: sourcing-pipeline
description: Work a CSV pipeline of partnership/hire targets — surface who still needs outreach, auto-tier talent rows, prep draft-only outreach on explicit ask. Use for "who's left on the sourcing list", "any targets to contact", pipeline reviews. Remind/assign only.
version: 1.1.0
---

# Sourcing Pipeline

Track a living list of partnership + hire targets and surface, every watch run,
who still needs outreach — tiered so the strongest names lead. The list is
config, not code: point the concern at any CSV.

## When to use

- "Who's left on the sourcing list?", "any partnership targets to contact?",
  "review the pipeline" — and every `ernest start` via concern
  `partnership-sourcing`.
- New target list → add a concern with this playbook via `/ernest-new-automation`
  and point its `source` at the CSV; don't fork the skill.
- NOT for: inbound leads (`b2b-lead-grading`), candidates already in the inbox
  (`candidate-followup`), or finding/ranking new people (`talent-sourcing-grading`
  — this skill *tracks* targets; that one discovers and ranks them).

## Parameters

Live in `memory/standing-concerns.md`, concern `partnership-sourcing`:

- `source` — CSV path relative to the profile (default `data/sourcing/targets.csv`).
- `purpose` — fallback for rows with an empty `purpose` column (engine default
  `outreach`; the shipped concern uses `partnership/hire`).

CSV columns (header row required): `name,linkedin,purpose,status,note,company,title,profile`.
`company`, `title`, `profile` feed talent grading — thin columns = weak tiers.

## Data sources (read-only; swappable)

| Need | VPS brain | Local MCP | Export |
|---|---|---|---|
| Target list | — | — | `data/sourcing/targets.csv` |
| Already-contacted evidence | `mcp__ernest-brain__search_mail` / `search_slack` / `search_hubspot` | mail/Slack/HubSpot connectors | `data/mail/`, `data/slack/`, `data/hubspot/` |

Engine baseline (no model, no connectors): `ernest start` / `python3 -m ernest.cli watch`.

## Watch half

1. **Read the list.** Every CSV row whose `status` is outside the done set is a
   candidate (blank status = `new` = candidate).
2. **Cross-check WIDE before surfacing.** For each candidate, search mail, Slack,
   and HubSpot for evidence outreach already happened — a thread with them, CRM
   activity, a Slack handoff. The engine can't see this; the model run must.
3. **Suppress the handled.** Already reached → drop from the card and add
   `- csv: PROPOSE status=contacted` so the row gets fixed (reversible L1 edit,
   applied only after the CEO nods — watch itself never mutates).
4. **Write ONE canonical card** (see `ernest-watch`) for the concern, tiered rows
   first. Remind/assign only — never put outreach content in a watch card.

## Decision criteria

Source of truth: `_sourcing_pipeline` in `ernest/watch.py` (**code wins**):

- **Done set** (skipped, case-insensitive): `contacted, done, reached, skip,
  skipped`. Anything else surfaces — including `warm`, `in progress`, typos.
- **Row purpose** = CSV `purpose` column, else the concern `purpose` param.
- **Auto-tiering**: only rows with purpose `hire` or `talent` run `grade_talent`
  (name + `profile` [falls back to `note`] + `company` + `title`) → a
  `[TIER-1/2/3]` badge in the title `[TIER-N] <name> (<purpose>)`. Partnership,
  press, and other purposes are never tiered.
- **Action**: tier rank < 2 (Tier-1/Tier-2) → `Review and assign outreach.`;
  everything else → `Likely skip (Tier-3); confirm before discarding.`
  **Quirk:** untiered rows (rank 9) get the "Likely skip (Tier-3)" wording too —
  on a partnership row that's the untiered default, not a real grade.
- **Sort**: tier rank ascending — tiered hires first, untiered rows last.
- **Missing CSV** → the concern yields no card at all, silently (see Failure modes).

| Symptom | Diagnosis | Knob | Where it lives |
|---|---|---|---|
| Contacted target keeps surfacing | status outside the done set | set `status` to `contacted`/`skip` | `data/sourcing/targets.csv` |
| No sourcing card at all | CSV path wrong or file gone (silent) | fix `source` / restore the file | `memory/standing-concerns.md` → `partnership-sourcing` |
| Hire rows tiered too low | empty `profile`/`title`/`company` | enrich those columns (grading reads them) | `data/sourcing/targets.csv` |
| Wrong tier vs. reality | rubric lists off | edit lists, never delete keys | `data/grading/talent-rubric.json` |
| Partnership rows should rank too | engine tiers hire/talent only | propose an engine change | `ernest/watch.py` (propose, don't hand-edit) |

## Draft half (explicit ask only)

Runs only on `draft these`, `/ernest-draft`, or a direct CEO instruction:

1. Ground first: `read-thread` any existing exchange with the target; read the
   `note`/`profile` columns and CRM history so the draft opens with something true.
2. Voice from `memory/ceo-persona.md`; no invented familiarity, no fake claims.
3. One draft per approved target → `00-Drafts/`, each headed `STATUS: DRAFT`.
4. This is **L2**: outreach batches need CEO approval; Ernest never sends,
   connects, or messages a target. Hire/talent rows also honor
   `talent-sourcing-grading` hard rules (owner assigned, exclusions respected).

## Output

Canonical card — see `ernest-watch`. This skill's extra bullets (model runs):

- `- checked: mail,slack,hubspot` — cross-check trail per surfaced target.
- `- csv: PROPOSE status=contacted` — when evidence shows the row is stale.

Card ends with the standard line:

Reply draft these when you want me to prepare actions.

## Failure modes

- **Missing/renamed CSV = silence, not an error.** `ernest doctor` still shows
  `partnership-sourcing` enabled (`concerns.parse` WORKING); an enabled concern
  that never produces a card means the `source` path is broken — check the file,
  don't assume a clean pipeline.
- **Negated text still matches.** Grading is substring-based: a profile saying
  "No Big Tech, no startup" still scores the `startup` signal (the shipped
  Sergei Orlov sample grades Tier-2 exactly this way). Read the profile before
  acting on a tier.
- **Missing `data/grading/talent-rubric.json`** → silent fallback to code-default
  lists; `ernest doctor` flags it (`grading.talent`, BROKEN).
- **Renamed/missing columns** → rows surface untier-ed as `Target (<purpose>)`
  with empty context. Fix the header row before adding more data.

## Verification

Transcribed from a real sandbox run (shipped sample data):

```bash
export ERNEST_PROFILE_DIR=$(mktemp -d)/p ERNEST_LOCAL_VAULT=$(mktemp -d)/v \
  ERNEST_MODE=local ERNEST_TODAY=2026-06-25 PYTHONPATH=$PWD
mkdir -p $ERNEST_PROFILE_DIR && cp -R data memory $ERNEST_PROFILE_DIR/
python3 -m ernest.cli watch
```

`partnership-sourcing--2026-06-25.md` shows `items: 5`, sorted:
`## 1. [TIER-1] Dmitry Volkov (hire)` → `- action: Review and assign outreach.`;
`## 4. [TIER-3] Target Beta (hire)` and `## 5. Target Alpha (partnership)`
(untiered, sorted last) both → `- action: Likely skip (Tier-3); confirm before
discarding.` `Target Closed` (`status: contacted`) is absent. Delete the CSV and
re-run: no sourcing card is written — the silent-miss failure mode above.
