---
name: slack-task-tracker
description: Transparent company task tracking from Slack — surface every open task by owner and flag overdue ones so nothing silently stalls. Remind/assign only; owner nudges become L2 drafts on explicit ask, never posted.
version: 1.1.0
---

# Slack Task Tracker

Make ownership transparent: anyone flags work in Slack, Ernest tracks who owns
what, what's due, and what's overdue. Two silent traps to guard: a **missing
source file produces no card at all** (looks like a clean day), and a
**malformed due date is silently treated as not overdue** (a late task shows as
merely `[OPEN]`). Both are yours to catch — the engine won't warn.

## When to use

Triggers: "what's overdue?", "who owns what?", "open tasks by owner", "did
anything stall?", "task status across the team", the `slack-task-tracking`
standing concern on a watch run.

Not for: replies the CEO owes on Slack threads (that's the `slack-open-threads`
concern → `account-followup-recovery`), full project management (this is
lightweight ownership + overdue surfacing), or auto-posting summaries to
channels — posting anything to Slack is approval-gated.

## Parameters

Engine playbook `task-tracker` (`ernest/watch.py::_task_tracker`). The concern
lives in `memory/standing-concerns.md` — change it by asking Ernest.

| Param | Default | Meaning |
|---|---|---|
| `source` | — (required) | task CSV path relative to the profile dir |

Live concern: `slack-task-tracking` with `source: data/slack/tasks.csv`.

Row schema `task,owner,status,due,source` with per-row defaults: empty
`status` → `open`, empty `owner` → `unassigned`; `due` must be `YYYY-MM-DD`;
`source` is the origin reference (e.g. `#partnerships`).

## Data sources (read-only; swappable)

| Need | VPS brain | Local MCP | Export fallback |
|---|---|---|---|
| Tasks | `mcp__ernest-brain__search_slack` | Slack MCP | `data/slack/tasks.csv` |
| Thread context for cross-check | `mcp__ernest-brain__search_slack` / `search_mail` / `search_hubspot` | Slack/Gmail/HubSpot MCP | `data/slack/threads/`, `data/mail/`, `data/hubspot/` |

Engine baseline: `ernest start` (or `python3 -m ernest.cli watch`) runs the
concern over the exported CSV with no model and no connectors.

## Watch half

1. **Verify the source exists** and count rows — a missing file yields no card
   and no error, so say "source unreadable" rather than staying silent.
2. **Search wide.** Read the task rows, then pull the surrounding evidence:
   the Slack thread each `source` points at, plus mail/HubSpot/calendar for the
   same commitment (a "send deck" task may have been closed by an email).
3. **Cross-check each open task for resolution elsewhere** before flagging:
   deliverable shipped in a Slack thread, reply already sent by mail, deal
   advanced in HubSpot, meeting already happened on calendar.
4. **Suppress** tasks resolved elsewhere. If resolved but the CSV row still
   says `open`, note it on the card as a proposed status flip (`status ->
   done`) — propose, don't silently rewrite the tracker.
5. Write **ONE canonical card** (format: `ernest-watch`). The engine keeps CSV
   row order; when you write or summarize, lead with `[OVERDUE]` items. Also
   flag rows whose `due` doesn't parse (see Decision criteria). Remind only.

## Decision criteria

Engine rule (code wins — `ernest/watch.py::_task_tracker`):

- Done-set (lowercased `status`): **{done, closed, cancelled, canceled}** —
  these rows are suppressed entirely. Any other status surfaces: `open` →
  `[OPEN]`, `blocked` → `[BLOCKED]`, a typo like `complete` → `[COMPLETE]`
  (still on the card — the done-set is exact-match, not semantic).
- Overdue ⇔ `due` is non-empty AND parses as `%Y-%m-%d` AND `due < today`
  **strictly** — due *today* is not overdue.
- A malformed `due` raises `ValueError` internally and is treated as **not
  overdue, silently**. You must flag such rows yourself (add a `- check: due
  unparseable` bullet) — a late task with `06/20/2026` looks merely open.
- Card title: `[OVERDUE|<STATUS>] <task> -> <owner>`; action is always
  `Track to done; nudge <owner> if stalled.`; `- context:` carries `source`.
- Missing source file → the playbook returns nothing → **no card at all**.

| Symptom | Diagnosis | Knob | Where it lives |
|---|---|---|---|
| Overdue task shows `[OPEN]` | `due` not `YYYY-MM-DD` | fix the date format | rows in `data/slack/tasks.csv` (or the Slack export step) |
| Card silently absent | source file missing/renamed, or every row in the done-set | `source` path; row count | concern in `memory/standing-concerns.md`; `data/slack/tasks.csv` |
| Finished task still carded | status wording not in the done-set (`complete`, `shipped`) | use `done`/`closed`/`cancelled`, or map on export | `data/slack/tasks.csv` |
| Everything `-> unassigned` | `owner` column left empty at capture | fill owner when the task is logged | `data/slack/tasks.csv` / Slack capture step |

## Draft half (explicit ask only)

Runs only on "draft these" / "nudge them" / `/ernest-draft`. This is **L2**:

1. Ground each nudge in the task's origin thread (`read-thread` on the
   `source` reference) — what was promised, to whom, current state.
2. Voice from `memory/ceo-persona.md`; one short nudge per stalled owner,
   written to `00-Drafts`, `STATUS: DRAFT`.
3. **Never post.** Sending a nudge DM, posting a daily "open/overdue by owner"
   channel summary, or turning a Slack message/reaction into a new tracked
   task are all external writes — each needs the CEO's approval of the exact
   message/row first. Reading Slack threads for grounding is fine (L0).

## Output

The engine card is canonical — field contract in `ernest-watch`. Model-written
cards and every chat summary add per-item extra bullets after the standard
ones: `- owner: <owner>` and `- due: <YYYY-MM-DD>` (plus `- check: due
unparseable` where it applies). End with exactly:

`Reply draft these when you want me to prepare actions.`

## Failure modes

- **Missing source ⇒ silent no-card** (observed): in a fresh sandbox with
  `data/slack/tasks.csv` removed, `watch` wrote 9 cards and no
  `slack-task-tracking--*.md` — indistinguishable from "no open tasks" unless
  you check. No `ernest doctor` check covers this file (doctor's `data.mail`
  covers only mail exports), so Watch step 1's existence check is the guard.
- **Malformed due ⇒ silently not overdue** (observed): a row due `06/20/2026`
  with today = 2026-06-25 rendered as `## 1. [OPEN] Ship pricing page ->
  web-lead` — five days late, no `[OVERDUE]`. Detection: parse every `due`
  yourself and flag non-`%Y-%m-%d` values.
- **Done-set is literal**: `complete`/`shipped`/`n/a` rows keep surfacing
  forever. Fix the status wording, not the engine.
- **Stale card in the vault**: watch never deletes old cards, so a same-day
  rerun after removing the source leaves the *previous* card file on disk —
  check the run output, not just the directory listing.

## Verification

Transcribed from a real run (2026-07-19, repo root):

```bash
export ERNEST_PROFILE_DIR=$(mktemp -d)/p ERNEST_LOCAL_VAULT=$(mktemp -d)/v \
       ERNEST_MODE=local ERNEST_TODAY=2026-06-25 PYTHONPATH=$PWD
mkdir -p $ERNEST_PROFILE_DIR && cp -R data memory $ERNEST_PROFILE_DIR/
python3 -m ernest.cli watch
```

Prints `Watch: wrote 10 card(s)` including
`…/00-Watch/slack-task-tracking--2026-06-25.md` with `items: 3` (the `done` row
"Publish Q2 press update" suppressed), containing:

```
## 1. [OVERDUE] Send partnership deck -> deal-lead
- why: Overdue task owned by deal-lead, due 2026-06-24.
- action: Track to done; nudge deal-lead if stalled.
- context: #partnerships

## 2. [OPEN] Follow up with Apex Bank on expansion -> ceo
```

plus `## 3. [OVERDUE] Reply to Jordan Lee (B2B growth role) -> recruiting-lead`.
Failure-mode checks in a throwaway copy: a row due `06/20/2026` rendered
`[OPEN]` (malformed-date trap) with the `cancelled` row suppressed; deleting
`tasks.csv` in a fresh sandbox produced no task card at all. If your output
differs, the fixture or `_task_tracker` changed — re-read both.
