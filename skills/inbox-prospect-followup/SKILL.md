---
name: inbox-prospect-followup
description: Watch the inbox for prospect threads (partnership/sales/investor/press) still owed a first follow-up; remind only, dedupe against b2b-candidates. Drafts only on explicit ask ("draft these"); never sends without approval.
version: 1.1.0
---

# Inbox Prospect Follow-Up

Find people in the CEO's inbox who match a target profile and still owe a first
follow-up — without inventing prospects and without double-reporting candidates.

## When to use

- "Who's waiting on me?", inbound prospect sweeps, "did I drop that partnership
  intro?", and the `inbox-prospects` standing concern on every watch run.
- NOT for: broad cold prospecting with no thread history (fails `min_signal`),
  hiring candidates (they belong to `b2b-candidates` / `hiring-pipeline`), or
  long-window audits ("full year" → `mail-deep-audit` / `ernest audit`).

## Parameters

```yaml
profile: "inbound B2B and partnerships"
intent: "partnership"      # PREFERENCE, not a filter — see Decision criteria
window: "90d"              # engine default 90d when unset
min_signal: "1 real exchange"
dedupe_against: "b2b-candidates"   # card id; plus optional HubSpot list/owner
card_id: "inbox-prospects"
```

`profile`, `intent`, `window` live in `memory/standing-concerns.md` under the
`inbox-prospects` concern (change by talking to Ernest — never hand-edit YAML).
`min_signal` and the dedupe rule live in this file.

## Data sources (read-only; swappable)

| Need | VPS brain -> local MCP | Export fallback |
|---|---|---|
| Mail threads + intent labels | `mcp__ernest-brain__search_mail` -> local mail MCP | `data/mail/**` (label `source: local-export`) |
| Dedupe + tier context | `mcp__ernest-brain__search_hubspot` -> HubSpot MCP | `data/hubspot/**` |
| Answered-elsewhere cross-check | `mcp__ernest-brain__search_slack` -> Slack + Calendar MCP | `data/slack/**`, `data/calendar/**` |

Engine baseline: `ernest start` (or `python3 -m ernest.cli watch`) runs this
playbook deterministically via `_inbox_prospect` in `ernest/watch.py`.

## Watch half

1. Read threads first (`ernest read --owed`) so decisions use full message
   bodies, not metadata.
2. Search mail for `profile` matches inside `window`; require `min_signal` —
   never manufacture a cold prospect.
3. Keep only threads that are **owed** (see Decision criteria).
4. **Cross-check** the other tools before flagging: answered in Slack, meeting
   booked on calendar, or deal advanced in HubSpot → suppress; stale CRM →
   add `- crm: PROPOSE <update>` instead (never auto-applied).
5. **Dedupe**: drop candidate/hire threads (that is `b2b-candidates` material)
   and anything matching `dedupe_against`.
6. Write ONE canonical card (`ernest-watch` format), id `inbox-prospects`.

No drafts in watch mode.

## Decision criteria

Engine-true (`_inbox_prospect`, `ernest/watch.py`):

- **owed** — the thread's last message is inbound with no later outbound reply.
  Not owed → never surfaces, whatever the intent.
- **window** — waiting days ≤ `window` (default 90d).
- **`intent` is a PREFERENCE, not a filter** (verified quirk): a thread passes
  when `intent` is unset, OR matches, OR the thread's intent is in
  `_TARGET_INTENTS = {partnership, sales, investor, press, hire, inbound}`.
  With `intent: "partnership"` configured, sales/hire/investor/press threads
  still pass — so candidate (`hire`) threads CAN co-appear here and on the
  `b2b-candidates` card.
- **Suppression rule** (apply in every summary): candidate/hire threads belong
  on `b2b-candidates` — report them there once, not twice. Anything resolved in
  another channel is suppressed, with the trail noted (`- checked:`).
- **Ranking**: the engine emits items unranked (source order). When
  summarizing, rank by `b2b-lead-grading` tier, then waiting days — tier-1 and
  oldest first.

| Symptom | Diagnosis | Knob | Where it lives |
|---|---|---|---|
| Non-partnership intents on the card | preference-not-filter, by design | suppress in summary, or narrow the concern | `memory/standing-concerns.md` → `inbox-prospects.params.intent` |
| Ancient threads resurfacing | window too wide | `window` (90d) | same concern params |
| No-history "prospects" appear | signal bar too low | `min_signal` (1 real exchange) | `## Parameters` here |
| Same person on two cards | dedupe skipped | `dedupe_against: b2b-candidates` | this skill's suppression rule |

## Draft half (explicit ask only)

Runs only on "draft these" / `/ernest-draft` / a direct CEO instruction.

1. Load card items (or re-run the search); pull full thread + HubSpot context +
   CEO voice exemplars (`memory/ceo-persona.md`; thin voice samples = say so).
2. Draft concise replies referencing the actual prior exchange; batch to
   `00-Drafts/`, `STATUS: DRAFT`, approval **L2**. Never send; HubSpot
   creates/updates are proposals only.
3. **Draft-quality bar — every draft passes all six, or rewrite:**
   1. **One reason** for reaching out — a single "why now" tied to their last message.
   2. **One relevant proof point** — verifiable, matched to what they asked about.
   3. **One low-friction CTA** — a question or a 15-minute slot, not a contract-sized ask.
   4. **Every personalization claim source-backed** — thread, CRM, or their site — or marked `unknown`.
   5. **No fake familiarity** — no "great chatting" when no chat happened; tone matches the real relationship depth.
   6. **Grounded in the full thread** (`ernest read`); export-based drafts carry "verify against the live inbox before sending".

## Output

Canonical reminder card (`ernest-watch` defines the format), id
`inbox-prospects`. Skill-specific extra bullets, kebab-short: `- tier:` (from
grading) · `- checked: mail,slack,hubspot,calendar` · `- dedupe: on
b2b-candidates` · `- crm: PROPOSE <update>`. Every card and chat summary ends
with:

`Reply draft these when you want me to prepare actions.`

## Failure modes

- **Intent mislabeled in exports** → wrong preference bucket or a missed
  prospect. Detect by spot-reading flagged threads (`ernest read`); log the
  correction with `ernest feedback`.
- **Prospect already answered in another channel** → mail says owed while
  Slack/calendar/HubSpot say handled; cross-check before flagging or the card
  cries wolf.
- **Candidate co-appearance** → the same person on `inbox-prospects` AND
  `b2b-candidates` in one brief means dedupe was skipped (the quirk, undetected).
- **Stale or missing mail exports** → a silently thin card; `ernest doctor`
  flags missing exports (`data.mail` check).

## Verification

Transcribed from a real sandbox run:

```bash
export ERNEST_PROFILE_DIR=$(mktemp -d)/p ERNEST_LOCAL_VAULT=$(mktemp -d)/v \
       ERNEST_MODE=local ERNEST_TODAY=2026-06-25 PYTHONPATH=$PWD
mkdir -p $ERNEST_PROFILE_DIR && cp -R data memory $ERNEST_PROFILE_DIR/
python3 -m ernest.cli watch
```

Prints `Watch: wrote 10 card(s)`, including
`.../00-Watch/inbox-prospects--2026-06-25.md` (trimmed):

```markdown
# Watch: inbox-prospects (2026-06-25)

type: reminder-card
source: local-export
items: 3

Remind/assign only. Say "draft these" if you want draft-only outreach prepared.

## 1. Dana Whitfield - Brightline Creative
- waiting: 3d
- why: Inbound sales lead waiting 3d.
- action: Qualify and send a first follow-up.

## 2. Jordan Lee - (independent)
- waiting: 4d
- why: Inbound hire lead waiting 4d.
```

The quirk, live: the concern is configured `intent: "partnership"`, yet a
**sales** lead (Dana Whitfield) and a **hire** lead (Jordan Lee) both pass —
and Jordan Lee appears again on `b2b-candidates--2026-06-25.md`. A correct
summary keeps Dana + Jordan Rivera (partnership, item 3) here and suppresses
Jordan Lee as "on b2b-candidates". If your card shows only exact-intent
matches, the engine changed — re-read `_inbox_prospect` before trusting this
section.
