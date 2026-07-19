---
name: add-collaborator
description: Flag threads in a watched category (e.g. B2B) where the designated teammate is missing from participants, so follow-ups don't die with the CEO. Use for "is Alex on all the B2B threads?" / collaborator coverage. Remind only; adding someone to a thread is L2.
version: 1.1.0
---

# Add Collaborator To Threads

The CEO opens doors; a teammate keeps them open. This skill watches a thread
category and flags every live thread the designated collaborator isn't on —
because a thread only the CEO can answer is a follow-up waiting to be dropped.

## When to use

- "Is Alex on all the B2B threads?", "collaborator coverage" — and every
  `ernest start` via concern `b2b-collaborator-coverage`.
- Watch a second person or category → add another concern with this playbook via
  `/ernest-new-automation`; don't fork the skill.
- NOT for: deciding who should own a deal (CRM/owner hygiene), or chasing the
  reply itself (`account-followup-recovery`).

## Parameters

Live in `memory/standing-concerns.md`, concern `b2b-collaborator-coverage`:

- `collaborator` — the teammate to check for (current: `Alex`). Empty = every
  thread in the category flags (see Failure modes).
- `category` — thread category to watch (current: `b2b`). Empty = all
  categories, card wording becomes "Key thread".

## Data sources (read-only; swappable)

| Need | VPS brain | Local MCP | Export |
|---|---|---|---|
| Threads + participants | `mcp__ernest-brain__search_mail` | Gmail connector | `data/mail/*.md` (`participants:` header) |
| Covered-elsewhere evidence | `search_slack` / `search_hubspot` | Slack, HubSpot connectors | `data/slack/`, `data/hubspot/` |

Engine baseline (no model, no connectors): `ernest start` / `python3 -m ernest.cli watch`.

## Watch half

1. **Search wide.** All threads in `category` across mail, with each thread's
   participant list — not just the inbox view.
2. **Cross-check before flagging.** An engine-flagged thread may still be
   covered: the collaborator runs a parallel thread with the same people, owns
   the HubSpot deal, or coordinates it in Slack. Covered elsewhere → **suppress**.
   Dead/closed threads → suppress too; coverage only matters on live threads.
3. **Verify `participants: unknown` items** (empty header in the export) against
   the real thread before surfacing — the export may simply be missing the
   header. Can't verify → surface WITH that caveat, never as a confident miss.
4. **Write ONE canonical card** (see `ernest-watch`). Remind only — the card
   asks to add them; the loop-in message itself is draft-half work.

## Decision criteria

Source of truth: `_add_collaborator` in `ernest/watch.py` (**code wins**):

- **Category filter**: threads whose `category` differs are skipped (when the
  param is set).
- **Coverage test**: flag unless `collaborator` is a case-insensitive
  **substring of any participant** — `alex` in `Alex Kim` counts as covered.
- **Substring cuts both ways**: `Alex` also matches `Alexandra`, so a different
  person can silently suppress the flag. Prefer a distinctive form (full name).
- **No owed/waiting logic**: unlike the follow-up playbooks this flags
  regardless of who spoke last — coverage, not staleness. The card has no
  `- waiting:`/`- tier:` bullets.
- **Detail line** = `- context: participants: <comma list>` or
  `participants: unknown` when the export has no header.
- **The act is L2**: adding someone to a live external thread (forward/CC)
  changes an external system — draft + CEO approval, never automatic.

| Symptom | Diagnosis | Knob | Where it lives |
|---|---|---|---|
| Covered thread still flagged | `participants:` header empty/stale in export | fix the header; verify before nudging | `data/mail/<thread>.md` |
| Wrong teammate watched | `collaborator` stale | update the param | `memory/standing-concerns.md` → `b2b-collaborator-coverage` |
| Wrong / too many threads | `category` too broad or empty | set `category` | same concern |
| Missing flag (wrong "Alex") | substring matched another name | use a distinctive full name | same concern (`collaborator`) |

## Draft half (explicit ask only)

Runs only on `draft these` or a direct CEO ask:

1. `read-thread` the FULL thread first — the loop-in note must summarize the
   real state: who wants what, what's been promised, the next step.
2. Draft the forward/CC note in `memory/ceo-persona.md` voice: one short intro
   handing the collaborator context and the follow-up baton.
3. Drafts → `00-Drafts/`, each headed `STATUS: DRAFT`.
4. **L2**: the CEO approves and sends/CCs himself; Ernest never modifies a live
   thread or invites anyone into it.

## Output

Canonical card — see `ernest-watch`. This skill's extra bullet (model runs):

- `- checked: mail,slack,hubspot` — coverage cross-check trail per thread.

Card ends with the standard line:

Reply draft these when you want me to prepare actions.

## Failure modes

- **Empty participants ≠ missing collaborator.** Exports without a
  `participants:` header always flag, as `participants: unknown` — verify
  against the real thread before nudging anyone. The shipped `agency-enterprise`
  sample reproduces this on every run.
- **Substring false-negatives.** `Alex` inside `Alexandra` reads as covered —
  the one miss the engine can't see; catch it by scanning the participant lists
  on the card and keeping `collaborator` distinctive.
- **Empty `collaborator` floods the card** — every thread in the category
  flags. The fix is the param, not disabling the concern.
- **Detection**: `ernest doctor` proves the concern is enabled (`concerns.parse`)
  and mail exports exist (`data.mail`); it cannot validate participant headers —
  that verification is the model's cross-check job in the Watch half.

## Verification

Transcribed from a real sandbox run (shipped sample data):

```bash
export ERNEST_PROFILE_DIR=$(mktemp -d)/p ERNEST_LOCAL_VAULT=$(mktemp -d)/v \
  ERNEST_MODE=local ERNEST_TODAY=2026-06-25 PYTHONPATH=$PWD
mkdir -p $ERNEST_PROFILE_DIR && cp -R data memory $ERNEST_PROFILE_DIR/
python3 -m ernest.cli watch
```

`b2b-collaborator-coverage--2026-06-25.md` shows `items: 2`:
`## 1. Brightline Creative - Enterprise rollout for our ad agency` with
`- context: participants: unknown` (the verify-first case), and
`## 2. Acme Corp - Intro - Acme x partnerships` with
`- context: participants: Sam, Priya Shah` and
`- action: Add Alex to this thread so the follow-up isn't dropped.`
The Horizon Ltd thread (`participants: Sam, Alex, Wei Chen`) is correctly
absent — Alex is already on it.
