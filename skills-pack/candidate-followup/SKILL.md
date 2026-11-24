---
name: candidate-followup
description: Surface inbox candidates (category candidate / intent hire) still owed a reply and assign reach-out to named owners. Use for "any candidates waiting on us?", hiring-inbox triage, the b2b-candidates concern. Remind/assign only; drafts on explicit ask.
version: 1.1.0
---

# Candidate Follow-Up

Candidates who write in and hear nothing go cold — and talk. This skill catches
every inbox candidate still owed a reply and puts a named owner on the
reach-out, before the CEO has to remember them.

## When to use

- "Any candidates waiting on us?", "who's in the hiring inbox?" — and every
  `ernest start` via concern `b2b-candidates`.
- NOT for: sourcing or ranking a pool (`talent-sourcing-grading`), ATS stage
  hygiene (`hiring-pipeline`), or non-hire inbound (`b2b-lead-grading`). This
  card is **unranked**; when a surfaced candidate has a profile, tier them via
  `talent-sourcing-grading` (`ernest grade --talent`) to pick outreach order.

## Parameters

Live in `memory/standing-concerns.md`, concern `b2b-candidates`:

- `role` — label used in card title/reason (engine default `candidate`).
  **A label, not a filter** — every candidate/hire thread matches regardless of
  what role the person is actually after.
- `assignees` — comma list named in the action (empty → `the hiring owner`).
- `window` — max days waiting to surface (default `180d`).

## Data sources (read-only; swappable)

| Need | VPS brain | Local MCP | Export |
|---|---|---|---|
| Candidate threads | `mcp__ernest-brain__search_mail` | Gmail connector | `data/mail/*.md` with `category: candidate` or `intent: hire` |
| Handled-elsewhere evidence | `search_slack` / `search_hubspot` | Slack, Ashby, Calendar connectors | `data/slack/`, `data/ashby/`, `data/calendar/` |

Engine baseline (no model, no connectors): `ernest start` / `python3 -m ernest.cli watch`.

## Watch half

1. **Search wide.** Candidate threads across mail — plus Slack hiring channels
   and the ATS (see `hiring-pipeline` sources) so nothing hides outside the inbox.
2. **Cross-check for resolution before flagging.** Interview already on the
   calendar? ATS stage advanced? A teammate replied in Slack or a different mail
   thread? Handled elsewhere → **suppress**; handled but the ATS/CRM is stale →
   keep it off the card and **propose** the update (draft-first, never auto).
3. **Surface only genuinely-owed candidates** within `window`, each with the
   configured assignees.
4. **Write ONE canonical card** (see `ernest-watch`) for the concern.
   Remind/assign only — no candidate-facing content in a watch card.

## Decision criteria

Source of truth: `_candidate_followup` in `ernest/watch.py` (**code wins**):

- **Is a candidate**: `category == "candidate"` OR `intent == "hire"`.
- **Owed**: the thread has an inbound and no later outbound. Missing
  `last_inbound`/`last_outbound` headers → never owed → silent miss.
- **Window**: `days_waiting <= window` (default 180d). Older candidates are
  filtered out silently, not marked stale.
- **No staleness floor**: unlike `dropped-followups` (7d threshold), a candidate
  surfaces from day 0 — candidate experience beats inbox patience.
- **Action text**: `Assign reach-out to <assignees>`, else `the hiring owner`.
- **Order**: as loaded, unranked. Ranked outreach order comes from
  `talent-sourcing-grading` — candidates with profiles get tiered there.

| Symptom | Diagnosis | Knob | Where it lives |
|---|---|---|---|
| Known candidate missing from card | export lacks `category: candidate`/`intent: hire` or inbound date | fix the thread headers | `data/mail/<thread>.md` |
| Older candidate vanished | past `window` (silent filter) | widen `window` | `memory/standing-concerns.md` → `b2b-candidates` |
| Wrong owner in action | `assignees` stale | update `assignees` | same concern |
| Title shows wrong role | `role` is only a label | update `role` | same concern |
| Need outreach order, card unranked | engine doesn't tier this card | `ernest grade --talent` | `data/grading/talent-rubric.json` |

## Draft half (explicit ask only)

Runs only on `draft these` or a direct CEO ask:

1. `read-thread` the FULL candidate thread first — draft on what they actually
   said, not the summary line.
2. Two draftables: the internal assignment ping to the named assignees, and (on
   ask) the candidate-facing reply in `memory/ceo-persona.md` voice.
3. All drafts → `00-Drafts/`, each headed `STATUS: DRAFT`.
4. Candidate-facing sends are **L2** — batched for CEO approval, never sent by
   Ernest. Compensation, offers, anything binding: **L3**, manual only.

## Output

Canonical card — see `ernest-watch`. This skill's extra bullets (model runs):

- `- assignee: <owner>` — who the reach-out is assigned to.
- `- checked: mail,slack,ashby,calendar` — resolution cross-check trail.

Card ends with the standard line:

Reply draft these when you want me to prepare actions.

## Failure modes

- **Header-dependent matching.** An export without `category: candidate` /
  `intent: hire`, or without `last_inbound`, never matches — a silent miss.
  `ernest doctor` (`data.mail`) proves exports exist, not that headers are
  right; spot-check one known candidate after any export refresh.
- **Window is a silent filter.** A candidate at day 181 disappears without a
  trace. For "did we ever answer X?" questions, use `ernest audit` / a wider
  window instead of trusting the daily card.
- **The engine can't see other tools.** A candidate advanced in the ATS or
  answered by a teammate in Slack still reads as owed in mail — the cross-check
  in the Watch half is what keeps this card honest; never skip it in a model run.

## Verification

Transcribed from a real sandbox run (shipped sample data):

```bash
export ERNEST_PROFILE_DIR=$(mktemp -d)/p ERNEST_LOCAL_VAULT=$(mktemp -d)/v \
  ERNEST_MODE=local ERNEST_TODAY=2026-06-25 PYTHONPATH=$PWD
mkdir -p $ERNEST_PROFILE_DIR && cp -R data memory $ERNEST_PROFILE_DIR/
python3 -m ernest.cli watch
```

`b2b-candidates--2026-06-25.md` shows `items: 1` and exactly:
`## 1. Jordan Lee - B2B marketing/sales`, `- waiting: 4d`,
`- why: Inbound B2B marketing/sales candidate waiting 4d, no follow-up.`,
`- action: Assign reach-out to recruiting-lead, sales-lead.`,
`- thread_id: candidate-dana`. Different assignees/role in your output means the
concern params changed — re-read `memory/standing-concerns.md` before trusting
the card.
