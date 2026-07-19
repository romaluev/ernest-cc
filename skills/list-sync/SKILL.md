---
name: list-sync
description: Reconcile who appears in email (by category) against a canonical list — HubSpot export or tracker sheet — and flag contacts missing from it. Remind-only; row additions become L2 draft proposals on explicit ask.
version: 1.1.0
---

# List Sync

Keep a curated list (a CRM segment, a press tracker sheet) aligned with who
actually shows up in email. The #1 way this skill loses trust is the
**broken-target false alarm**: if the target file is missing or misread, the
engine flags EVERY contact in the category as "missing from the list".
**"Everything is missing" is a broken-target symptom, not a finding** — verify
the target before believing a big card.

## When to use

Triggers: "is the CRM list up to date?", "who's in email but not in HubSpot?",
"sync the press sheet", "did we add everyone from the regional intros?", the
`korea-list-sync` / `press-list-sync` standing concerns on a watch run.

Not for: grading or qualifying the contacts (`b2b-lead-grading`), chasing
unanswered threads (`account-followup-recovery`), or actually writing to the
CRM/sheet — this skill only ever *proposes* writes.

## Parameters

Engine playbook `list-sync` (`ernest/watch.py::_list_sync`). Concerns live in
`memory/standing-concerns.md` — change them by asking Ernest, never by
hand-editing YAML.

| Param | Default | Meaning |
|---|---|---|
| `category` | `""` = every thread | thread category to reconcile (`korea`, `press`, …) |
| `match_key` | `company` | thread field to look up (`company`, `contact`, `subject`, …) |
| `target` | — (required) | CSV path **relative to the profile dir** |
| `target_key` | `company` | CSV column holding the canonical values |
| `list_name` | the `target` path | human name printed on the card |

Live concerns: `korea-list-sync` (`category: korea`, `target:
data/lists/korea-hubspot.csv`, `target_key: company`, list name "Regional
HubSpot list") and `press-list-sync` (`category: press`, `target:
data/lists/press-sheet.csv`, `target_key: outlet` — note the cross-mapping:
thread **company** is matched against the sheet's **outlet** column).

## Data sources (read-only; swappable)

| Need | VPS brain | Local MCP | Export fallback |
|---|---|---|---|
| Threads + category | `mcp__ernest-brain__search_mail` | Gmail/mail MCP | `data/mail/*.md` (`category:` header) |
| Target list | `mcp__ernest-brain__search_hubspot` | HubSpot / Sheets MCP | `data/lists/*.csv` |

Engine baseline: `ernest start` (or `python3 -m ernest.cli watch`) runs every
enabled list-sync concern with no model and no connectors.

## Watch half

1. **Verify the target FIRST.** Resolve `target` against the profile dir, read
   it, and confirm row count > 0 and that the `target_key` column exists with
   non-empty values. If not, report "target unreadable — card suppressed"
   instead of flagging anyone (the engine can't do this guard; you must).
2. **Search wide.** Gather the category's threads from mail; also pull the same
   contacts from Slack and HubSpot so step 4 has something to check against.
3. **Compute the missing set** the way the engine does: lowercase+strip the
   thread's `match_key` value and every `target_key` cell; flag threads whose
   normalized value is absent. Threads with an **empty** `match_key` value are
   skipped silently — count them and note the count if > 0.
4. **Cross-check before flagging.** For each candidate: already in the *live*
   CRM (export just stale)? On the list under a name variant ("PacificCo Inc."
   vs "PacificCo")? A teammate confirmed adding them in Slack? → **suppress**;
   for a stale export, refresh the export rather than carding. Only
   genuinely-absent contacts survive.
5. Write **ONE canonical card** (format: `ernest-watch`) with the `- list:`
   extra bullet. Remind only — never touch the sheet or CRM in watch mode.

## Decision criteria

Engine rule (code wins — `ernest/watch.py::_list_sync`):

- Flag ⇔ thread matches `category` AND `match_key` value is non-empty AND
  `lower(strip(value))` ∉ {normalized `target_key` cells}.
- Matching is **exact after lowercase+strip** — no fuzzy matching, so suffix
  and spelling variants read as "missing". That's what step 4 exists to catch.
- Missing/unreadable target ⇒ the present-set is empty ⇒ **every** category
  thread flags. A wrong `target_key` name has the *same* symptom: every cell
  reads empty, the present-set stays empty, everything flags.
- No threads in the category ⇒ no items ⇒ **no card at all** (silent). A clean
  quiet day and a wrong `category` value look identical — check the `category:`
  headers in `data/mail/*.md` before trusting silence.

| Symptom | Diagnosis | Knob | Where it lives |
|---|---|---|---|
| Everything in the category flagged at once | target CSV missing, path wrong, or `target_key` column misnamed | `target` / `target_key` | concern in `memory/standing-concerns.md`; file under `data/lists/` |
| Contact flagged though they're on the list | name variant or wrong column pairing | normalize the sheet cell; check `match_key`→`target_key` pair | the target CSV + the concern |
| Card never appears | no threads carry the category, or category typo | `category`; add `category:` to thread exports | concern + `data/mail/*.md` |
| Wrong entity compared (people vs companies) | `match_key`/`target_key` mismatch | set the pair explicitly | concern in `memory/standing-concerns.md` |

## Draft half (explicit ask only)

Runs only on "draft these" / "add them" / `/ernest-draft`. This is **L2**:

1. Ground every field in the full thread (`read-thread` / `ernest read`) —
   name, company, email as actually written. A field you can't source is
   `UNKNOWN`, never invented.
2. Produce the exact rows in the target's own schema (e.g. `name,outlet,email`
   for the press sheet) as a reviewable proposal in `00-Drafts`, `STATUS:
   DRAFT`, one block per list.
3. Apply to HubSpot/the sheet only after the CEO approves those exact rows.
   Removing or overwriting existing list rows is an irreversible delete — L3,
   manual only.

## Output

The engine card is canonical — field contract in `ernest-watch`. Model-written
cards and every chat summary add the skill's extra bullets after the standard
ones: `- list: <list_name>`, and `- crm: PROPOSE add <who> to <list>` when the
live system is stale (a proposal, never auto-applied). End with exactly:

`Reply draft these when you want me to prepare actions.`

## Failure modes

- **Missing target ⇒ mass false alarm** (observed, not theoretical): in a
  sandbox with a second korea thread whose company *is* on the list, the card
  read `items: 1`; after `mv korea-hubspot.csv korea-hubspot.csv.bak` the rerun
  read `items: 2` — the on-list contact ("Hana Sato - StartupCo") was flagged
  too. Detection: sudden jump to ~all category threads + target row-count read.
- **Wrong `target_key`** produces the identical everything-flagged card — check
  the header row, not just the file's existence.
- **Silent skips**: empty `match_key` values and empty categories produce no
  card and no warning. No `ernest doctor` check covers `data/lists/*.csv`
  (doctor's `data.mail` covers only mail exports), so the row-count read in
  Watch step 1 is the only guard.
- **Stale export**: contact added to live HubSpot after the export was cut
  still flags. Cross-check (Watch step 4) suppresses it; refresh the export.

## Verification

Transcribed from a real run (2026-07-19, repo root):

```bash
export ERNEST_PROFILE_DIR=$(mktemp -d)/p ERNEST_LOCAL_VAULT=$(mktemp -d)/v \
       ERNEST_MODE=local ERNEST_TODAY=2026-06-25 PYTHONPATH=$PWD
mkdir -p $ERNEST_PROFILE_DIR && cp -R data memory $ERNEST_PROFILE_DIR/
python3 -m ernest.cli watch
```

Prints `Watch: wrote 10 card(s)` including `…/00-Watch/korea-list-sync--2026-06-25.md`
(`items: 1`), which contains:

```
## 1. Min-jun Park - PacificCo
- why: In email (korea) but missing from Regional HubSpot list.
- action: Add to Regional HubSpot list to keep email and the list in sync.
- context: Regional market intro
```

and `press-list-sync--2026-06-25.md` contains `## 1. Jane Editor - Major Outlet`
/ `- why: In email (press) but missing from Press tracker sheet.` Failure-mode
check: rename `$ERNEST_PROFILE_DIR/data/lists/korea-hubspot.csv` away and rerun —
the card jumps to `items: 2` with every korea thread flagged (see Failure
modes). If your numbers differ, fixtures or `_list_sync` changed — re-read both.
