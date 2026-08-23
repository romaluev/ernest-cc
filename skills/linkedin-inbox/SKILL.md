---
name: linkedin-inbox
description: Triage the CEO's LinkedIn DMs — surface promises he made and never kept, deadlines that already passed, who is genuinely waiting, escalate money/legal/security/churn/safety to a person, hold press and investors, and collapse cold sequences into one judgment. Report only; archiving happens on an approved named batch. Use for "what's in my LinkedIn messages", "who am I ignoring", "what did I promise", "clean up my LinkedIn DMs".
version: 1.0.0
---

# LinkedIn Inbox

An invitation asks *who is this*. A DM asks a different first question:
**am I the one holding this up.**

Report only. Archiving happens on an approved batch that names every thread.

Full decision spec — every list, weight and threshold: `docs/linkedin-spec.md`.

## When to use

"What's in my LinkedIn messages?", "who am I ignoring?", "what did I promise
anyone?", "anything urgent in my DMs?", "clean up my LinkedIn inbox", or a
scheduled sweep via `ernest start`.

## When NOT to use

| Request | Goes to |
|---|---|
| Pending connection invitations | `linkedin-invitations` |
| Email inbox | `inbox-prospect-followup`, `mail-deep-audit` |
| Sending outbound DMs | out of scope; nothing here sends |
| Mention / audience studies | the separate `linkedin-research` tool |
| Support tickets | `support-triage` |

## Prerequisites

```bash
python3 adapters/linkedin/ingest.py --doctor
```

`rungs_reachable` must be non-empty. **If it is empty, stop** and report the
remedy — an unread inbox and an unreachable one are different answers.

The message export is the easiest source and needs nothing installed: Settings →
Data Privacy → Get a copy of your data → tick **Messages**. It carries the full
text of every thread, which is what everything below reads.

## Parameters

```yaml
max_named: 15
owner_names: []              # defaults to memory/ceo-persona.md
commitment_floor: 12.0       # below this a promise is chatter
stale_commitment_days: 180
campaign_similarity: 0.45    # measured, see the spec
caps_per_day: {archive: 200, delete: 25}
never_auto: [delete, report_spam, reply, inmail]
```

`owner_names` matters more than it looks. **Misdetecting the account owner
inverts the direction of every message**, turning the CEO's own replies into
inbound mail and every thread into "owed". It is read from
`memory/ceo-persona.md`, falling back to whoever appears in the most *distinct
threads* — not the most messages, since one persistent spammer can out-message
the owner inside a single thread.

## Data sources (read-only; swappable)

| Need | VPS brain -> local MCP | Export fallback |
|---|---|---|
| Message threads | — (no LinkedIn MCP exists) | `data/linkedin/messages*.csv` |
| Who "we" are | — | `memory/ceo-persona.md` |
| CRM tier, open deal, won revenue, suppression | `mcp__ernest-brain__search_hubspot` -> HubSpot MCP | `data/hubspot/**` |
| Answered-elsewhere cross-check | `mcp__ernest-brain__search_mail` -> Gmail/Slack MCP | `data/mail/**`, `data/slack/**` |

Engine baseline: `ernest grade --linkedin` writes this card and the invitations
card together. The adapter runs outside the gate — see `docs/ingest-ladder.md`.

## Fallbacks

The same five-rung ladder as invitations. The archive rung carries **full
message text**, which is what commitments, deadlines and thread state all read,
so this surface degrades less than invitations do on rung 2.

Files are read from an allow-list. A real export drops `Invitations.csv`,
`Connections.csv` and `messages.csv` in one folder, and a deny-list once loaded
messages as invitations.

## Watch half

```bash
python3 adapters/linkedin/ingest.py --doctor    # 1. a rung must be reachable
python3 adapters/linkedin/ingest.py             # 2. walk the ladder
ernest grade --linkedin                         # 3. score, analyse, report
```

1. Group rows into threads; derive direction from the owner name.
2. Compute **owed**: their last message is newer than our last reply.
3. Value the counterparty (facts first — see Decision criteria).
4. Dig out what is buried: unkept commitments, deadlines, thread state.
5. **Cross-check** before saying someone is ignored — answered by email, on
   Slack, or a meeting booked → downgrade and note `- checked:`. The fastest way
   to lose trust is flagging a dropped thread that was handled elsewhere.
6. Write ONE card, id `linkedin-dms`, plus the CSV sidecar and the state file
   that powers next run's "what changed".

No replies, no archiving, no reporting in watch mode.

## Decision criteria

Engine-true (`grade_linkedin_dm` + `ernest/li_insight.py`). **Order is the
safety mechanism:**

```
escalation -> suppression -> hold -> replied-before -> owed+ICP -> job seeker -> spam -> FYI
```

| Branch | Rule | Bucket |
|---|---|---|
| **Escalation** | money/billing, legal, security, churn, safety | `escalation` |
| Suppression / Hold | lists `411` `400` `412` `413` `414` `485` `484`; press, legal, competitor, investor | `hold` |
| Replied before | we took part | never `trash` |
| Owed + ICP | they wrote last; archetype, intent, a question | `needs-reply` |
| Job seeker | its own lane | `fyi` |
| Spam | scored on the **opener** only | `trash` |
| Otherwise | nothing owed | `fyi` |

**Escalation outranks our own prior replies** — a refund dispute from a
long-standing customer is more urgent than one from a stranger, not less.

**Spam is scored on the opener.** Quoting a pitch back while declining it must
not make the thread read as the pitch. Spam never applies to a thread we
answered.

### Value, and what it gates

Facts (open deal 45, won revenue up to 40 log-scaled, CRM tier 30) outrank
inference (archetype 10, intent 9, seniority 7) by design. Bands:
`critical / high / medium / low / noise`.

**Unknown is a third state.** Without a company, title, CRM record, or a
conversation we joined, the person is `unknown` and capped at `low` — anyone can
type "enterprise rollout" into a cold DM. But an unknown stating real commercial
intent is flagged **WORTH IDENTIFYING** and surfaced separately: the next action
is a 30-second lookup, not a reply in the dark.

### What gets dug out

- **Unkept commitments** — promises *we* made, classified (legal 1.6 → intro
  0.9), valued by counterparty × type, ×1.8 if they chased. Dropped when already
  delivered, when an intro **names no subject** ("I'll intro you to someone" is a
  pleasantry, not a task), when the counterparty is unidentified or noise, when
  stale past 180d unchased, or below the floor.
- **Deadlines** — resolved against the date the message was written, never today.
- **Thread state** — stage, who owes whom, days quiet, blocking item. Stage cues
  only count if we actually replied.
- **Campaigns** — near-identical openers across senders become one judgment.
- **What changed** since the last run.

| Symptom | Diagnosis | Knob | Where |
|---|---|---|---|
| Everyone looks owed, our own replies read as inbound | owner name unmatched — directions inverted | `- Name:` line | `memory/ceo-persona.md` |
| A real conversation in spam | opener reads like a pitch | `spam.threshold`, `spam.vendor_keywords` | rubric JSON |
| Cold sequences reaching needs-reply | blast list thin | `spam.dm_blast_keywords` | rubric JSON |
| A billing complaint sorted as ordinary | escalation list too literal | `escalation.money_keywords` | rubric JSON |
| Trivial promises flooding the report | floor too low | `COMMITMENT_FLOOR` | `ernest/li_insight.py` |
| A no-name outranking a customer | facts missing from the CRM export | `open_deal`, `won_revenue` columns | `data/hubspot/**` |
| Report identical every morning | state file missing | `logs/linkedin-dms-state.json` | profile |

## Draft half (explicit ask only)

```bash
ernest grade --linkedin
python3 adapters/linkedin/act.py --caps
python3 adapters/linkedin/act.py --plan --dms --tier trash
python3 adapters/linkedin/act.py --execute <batch.json>
python3 adapters/linkedin/act.py --rescue <key> --actual needs-reply --why "..."
```

- **`escalation` and `hold` can never enter a batch**, by any route.
- **A thread still owed a reply is never bulk-archived** unless it is `trash`.
  Archiving something someone is waiting on is the failure that costs a deal.
- Archive is reversible; **delete is not** and sits under `never_auto`.
- Replies: the engine assembles a **reply brief** — their actual question, what
  we promised, the clock, thread state, what the reply must contain, and what it
  must not claim. The model writes the prose from that, in the CEO's voice, into
  `00-Drafts/` with `STATUS: DRAFT`, level **L2**. A brief for an unidentified
  person explicitly forbids inventing a relationship.
- Apply `inbox-prospect-followup`'s six-point draft bar.

## Output

Card id `linkedin-dms`, ordered by what costs most to get wrong:
escalations → **promises we broke** → **clocks that ran out** → who is waiting →
holds → campaigns → counts. Spam is a number at the bottom; it is the least of
it.

Extra bullets: `- value:` · `- state:` · `- said:` · `- we promised:` ·
`- clock:` · `- signal:` · `- checked:` · `- thread_id:`. Every card ends with:

`Reply draft these when you want me to prepare actions.`

## Exit codes

Shared with `linkedin-invitations`: `0` ok · `2` usage · `3` nothing to work on ·
`4` unreachable · `5` upstream · `6` refused by policy · `7` rate limited ·
`10` config.

## Edge cases

| Case | Behavior |
|---|---|
| Owner absent from `ceo-persona.md` | Falls back to most-distinct-threads; report which name was used |
| Two people share a display name | Keyed by conversation id, so they stay separate |
| Thread with only outbound messages | Dropped — nothing inbound to triage |
| Group thread | Counterparty per row; the thread stays one row |
| Sponsored InMail | Scored like any cold opener; no special case |
| LinkedIn already filed it spam | Adds evidence, does not decide alone |
| Long thread, we replied, now quiet | `fyi` — not owed, not spam |
| Escalation inside a thread we answered | Still `escalation`; the branch runs first |
| Promise we already delivered | Dropped, with the delivering message as evidence |
| "I'll intro you to someone" | Dropped — no named subject |
| Deadline written months ago | Resolved against then, reported as passed |
| Message text missing from the export | Scores on subject only; thin evidence flagged |
| Archive requested for an owed thread | Refused unless the bucket is `trash` |

## Failure modes

- **Inverted directions** — the worst one, and it looks like a working report.
  Detect it: if no thread across a real inbox shows `we have replied`, the owner
  name did not match.
- **Archiving something owed** — costs a deal silently. Two guards exist; do not
  bypass either.
- **Escalation missed by literal matching** — "charged me twice" is not the word
  "refund". Sample the `fyi` bucket for anything angry.
- **A promise dropped as vague that was real** — the intro gate is deliberately
  strict. Check `check:` reasons in the sidecar if something is missing.
- **Stale export read as live** — check `source:` and `.ingest.json`.

## Verification

Transcribed from a real sandbox run:

```bash
export ERNEST_PROFILE_DIR=$(mktemp -d)/p ERNEST_LOCAL_VAULT=$(mktemp -d)/v \
       ERNEST_MODE=local ERNEST_TODAY=2026-08-24 PYTHONPATH=$PWD
mkdir -p $ERNEST_PROFILE_DIR && cp -R data memory ernest.yaml $ERNEST_PROFILE_DIR/
python3 -m ernest.cli grade --linkedin
```

Writes `00-Watch/linkedin-dms--2026-08-24.md` (trimmed):

```markdown
## 1. [ESCALATION] Helena Marsh — low (18) — a conversation we took part in
- said: "We were charged twice for August. Can you sort out a refund?"
- action: Answer personally — do not delegate or template

## 2. [YOU PROMISED] Unkept commitments
- Lucas Silva — critical — pricing, 75d ago, **they chased**
    "I'll send the pricing sheet this week."
- Jordan Rivera — high — intro, 54d ago
    "I'll introduce you to Dana at Kestrel Media."

## 3. [CLOCK] Deadlines they set
- Lucas Silva — critical — "need it by end of month" -> 2026-06-30 (passed 55d ago)

## 6. [CAMPAIGN] 3 senders running the same sequence
```

The judgments, live: Helena's is a thread the CEO **had already replied to**, and
it still sorts first because escalation runs before the relationship branch. The
unsent pricing sheet outranks the intro because they chased it. A three-message
"Quick question / Just checking in / Circling back" sequence lands in spam
despite waiting 40 days — **waiting time is not evidence of legitimacy**.

Engine optional: with no `messages*.csv` the skill reports the ladder's honest
failure rather than an empty inbox.

Run the guarantees: `python3 tests/test_linkedin_insight.py`.
