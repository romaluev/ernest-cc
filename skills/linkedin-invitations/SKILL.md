---
name: linkedin-invitations
description: Triage the CEO's pending LinkedIn connection invitations — tier them against the ICP, separate spam from ambiguous strangers, hold press/investors/competitors for a human, and act only on an approved named batch. Use for "what's in my LinkedIn inbound", "clean up my invites", "who's worth accepting", "remove the LinkedIn spam", or a scheduled inbound sweep.
version: 1.0.0
---

# LinkedIn Invitations

Turn thousands of pending invitations into a page the CEO acts on in two minutes,
without accepting a competitor, ignoring a journalist, or reporting a customer as
spam.

Report first. Acting requires an approved batch that names every person.

## When to use

- "What's in my LinkedIn inbound?", "clean up my invitations", "who should I
  accept?", "remove the spam", a scheduled inbound sweep, or `ernest start`.

## When NOT to use

| Request | Goes to |
|---|---|
| LinkedIn DMs, InMail, message replies | `linkedin-inbox` (not built yet — say so) |
| Invitations *we* send, outbound prospecting | out of scope; nothing here sends |
| Mention / audience / creator studies | the separate `linkedin-research` tool — do not grow a second copy here |
| Grading email threads | `b2b-lead-grading` |
| Candidates and hiring | `talent-sourcing-grading` |
| Posting, commenting, reacting | never — no path in this skill writes to LinkedIn beyond accept/ignore |

## Prerequisites

**Verify before running anything. Do not proceed on a guess.**

```bash
python3 adapters/linkedin/ingest.py --doctor
```

Read `rungs_reachable` in the output:

| Result | Meaning | Do this |
|---|---|---|
| `[1,2,3,4]` | everything reachable | proceed |
| `[1,4]` only | no browser — snapshot and CRM mirror only | proceed, and say the data is not live |
| `[]` | nothing reachable | **stop.** Report the ladder's remedy; do not report an empty queue |

If no browser is reachable, install one — do not silently fall back to a stale file:

```bash
# preferred: isolated agent context, reuses the signed-in session
which ego-browser || echo "install ego-browser"

# or: attach to the CEO's real Chrome profile
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 --profile-directory=Default
python3 adapters/linkedin/ingest.py --doctor --prefer chrome
```

`ernest doctor` carries the same three checks: `linkedin.ingest`, `data.linkedin`,
`grading.linkedin`.

## Parameters

```yaml
max_named: 15            # invitations given their own card section; rest are bucketed
ingest_max_age_hours: 20 # older than this and the queue is refreshed
auto_ingest: false       # let `ernest start` refresh the queue itself
spam_threshold: 5.0      # structural evidence needed before Ignore is proposed
caps_per_day: {accept: 25, ignore: 100, report_spam: 25}
never_auto: [report_spam, reply, inmail]
dry_run: true            # master switch; acting also needs approved: true
```

Everything above lives in `ernest.yaml` under `linkedin_policy`, except
`spam_threshold`, which is `spam.threshold` in
`data/grading/linkedin-rubric.json` so `ernest learn` can tune it. Signal lists
live in that same JSON. Weights live in `ernest/grading.py` and are mirrored in
`references/rubric.md`.

## Data sources (read-only; swappable)

| Need | VPS brain -> local MCP | Export fallback |
|---|---|---|
| Pending invitations | — (there is no LinkedIn MCP) | `data/linkedin/*.csv` via `adapters/linkedin/ingest.py` |
| Suppression lists, CRM tier, prior contact | `mcp__ernest-brain__search_hubspot` -> HubSpot MCP | `data/hubspot/**` |
| Answered-elsewhere cross-check | `mcp__ernest-brain__search_mail` -> Gmail/Slack MCP | `data/mail/**`, `data/slack/**` |

The adapter runs **outside** this session. The gate blocks shell commands
carrying https URLs and turns off web tools in local mode; that is correct and is
not to be weakened. Engine baseline: `ernest grade --linkedin`.

## Fallbacks

Every rung reports which one produced the data, and that label rides through to
`source:` on the card. Never present one rung's output as another's.

| Rung | Mechanism | `source:` | Has headline/mutuals? | Can act? |
|---|---|---|---|---|
| 1 | fresh `data/linkedin/*.csv` | whatever wrote it | inherited | no |
| 2 | LinkedIn "Get a copy of your data" | `linkedin-archive` | **no** — blank, not zero | no |
| 3 | live invitation-manager DOM | `linkedin-live` | yes | yes |
| 4 | HubSpot `linkedin_*` properties | `hubspot-mirror` | partial | no |
| 5 | nothing worked | `unavailable` | — | no |

- **Rung 2 under-detects spam by design.** The archive carries no mutual count or
  network size, so structural spam evidence is thinner. That is the correct
  trade: under-detecting spam costs a scroll, over-detecting it costs a customer.
- **Rung 4 is always a subset** — HubSpot only knows people who already reached
  the CRM. Its count is not the size of the queue. Never read the `heyreach_*`
  family: 20 properties, empty portal-wide.
- **Rung 5 writes nothing.** An empty answer is a real answer; a fabricated one
  is not.

Browser fallback within rungs 2–3: `ego-browser`, then Chrome over CDP, then
raise. Same pattern for every future connector — see `docs/ingest-ladder.md`.

## Watch half

```bash
python3 adapters/linkedin/ingest.py --doctor      # 1. verify a rung is reachable
python3 adapters/linkedin/ingest.py               # 2. walk the ladder
ernest grade --linkedin                           # 3. score + write the card
```

1. Keep `direction=received`, `invitation_type=connect`. Company follows and
   newsletter subscriptions arrive on the same surface and inflate every count.
2. Dedupe by identity key — slug, then member URN, then normalized name.
3. Grade. **Suppression runs before any tier is assigned.**
4. Cross-check before proposing anything irreversible: already connected,
   already answered in mail or Slack, already a CRM contact with an owner ->
   downgrade the proposed action and note the trail with `- checked:`. Stale CRM
   -> `- crm: PROPOSE <update>`, never auto-applied.
5. Write one card (`ernest-watch` format), id `linkedin-invitations`, plus the
   CSV sidecar with the full population.

No accepts, no ignores, no spam reports in watch mode.

## Decision criteria

Engine-true (`grade_linkedin_inbound`, `ernest/grading.py`). **The order is the
safety mechanism and is not negotiable:**

```
suppression -> hold -> CRM tier -> tier-1 signals -> job seeker -> spam -> default tier-2
```

Checking tier before suppression is how a competitor or a journalist ends up
accepted and then sequenced. Reordering is a behavior change, not a refactor.

| Branch | Rule | Result |
|---|---|---|
| Suppression | list `411` is the union — check first. `400` `412` `413` `414` `485` `484` | `hold`; list `399` (employees) -> Accept, colleagues are not spam |
| Hold | press, legal, competitor, investor, claims a prior CEO conversation | `hold`, never auto-resolved either way |
| CRM tier | a known relationship | that tier, confidence `high`, score 100/60 |
| Tier-1 | needs a **who**: archetype, vertical, platform/API, provider, or major company | seniority, country, mutuals only amplify |
| Job seeker | its own lane | `tier-2`, signal `JOB_SEEKER` |
| Spam | **scored**, needs `spam.threshold` points of independent evidence | `trash` |
| Default | anything else | `tier-2`, low, flagged |

- **Missing is not zero.** Blank mutual count = "we did not look" and scores
  nothing. Only a real `0` is evidence.
- **Ranking:** tier rank (`tier-1`, `hold`, `tier-2`, `trash`), then score, then
  longest waiting.
- **Never a silent tier-1, never a silent trash. Do not over-trash** — an
  ambiguous stranger is tier-2 with a flag.

| Symptom | Diagnosis | Knob | Where it lives |
|---|---|---|---|
| Real buyers in the spam bucket | threshold too low, or a vendor phrase too broad | `spam.threshold`, `spam.vendor_keywords` | `data/grading/linkedin-rubric.json` |
| Obvious spam surfacing as tier-2 | threshold too high for this population | `spam.threshold` | same file |
| Everything grades tier-2/low | rubric missing or a key deleted | restore it | `ernest doctor` -> `grading.linkedin`, then `ernest heal` |
| A journalist or investor got an Accept | suppression ran after grading, or the list is stale | list membership | HubSpot `411`/`412`/`413` |
| Card is a wall of names | bucketing bypassed | `max_named_on_card` | `ernest.yaml` -> `linkedin_policy` |
| Counts impossibly small | rung 4 (partial CRM mirror) was used | re-run on rung 2 or 3 | `ingest.py --doctor` |
| Population exceeds LinkedIn's own pending count | dedupe skipped; slug and URN counted twice | `identity_key` | `ernest/grading.py` |
| Same batch keeps getting rescued | the grader is wrong, not the CEO | `act.py --rescue` 3x -> `ernest learn` proposes the diff | decision journal |

## Draft half (explicit ask only)

Runs only on "draft these" / "remove the spam" / a direct instruction. Never on a
schedule.

```bash
ernest grade --linkedin                                   # re-grade; do not trust a day-old proposal
python3 adapters/linkedin/act.py --caps                   # what is left today
python3 adapters/linkedin/act.py --plan --tier trash      # -> 00-Drafts/linkedin-ignore--<date>.json
# CEO reads the batch, deletes anyone who does not belong, then:
python3 adapters/linkedin/act.py --execute <batch.json>
python3 adapters/linkedin/act.py --rescue slug:<who> --actual tier-1 --why "<one line>"
```

- The batch names **every person by identity key**. "Ignore all the spam" has to
  survive being wrong about one person, so approval names them. A batch with an
  empty `items` list is refused.
- `dry_run: true` is the default and stays dry until `approved: true` as well.
- Caps are counted from the audit log, so a crashed run still counted.
- Pacing (`min_action_interval_seconds`) is a safety property, not politeness.
- Approval level **L2**. HubSpot writes stay proposals, using the portal's own
  `linkedin_inbound_invitation_status` and `linkedin_message_signal` values.

| Action | Reversible | Ceiling | Cap/day |
|---|---|---|---|
| Ignore | yes — they can re-invite | L1 after 3 clean runs | 100 |
| Accept | yes — remove the connection | L1 after 3 clean runs | 25 |
| Report spam / "I don't know this person" | **no**, and it affects their account | **L2 forever**, named list every run | 25 |
| Reply / InMail | no | out of scope here | — |

Promotion needs data *and* sign-off; **demotion on any incident is automatic**.
The asymmetry is deliberate — the documented failure mode is drift toward
unearned autonomy, not excessive caution.

## Output

Canonical reminder card (`ernest-watch` format), id `linkedin-invitations`, plus
`linkedin-invitations--<date>.csv` with the full population. Tier-1 and hold get
their own sections up to `max_named`; everything else is a `[BUCKET]` row with a
count and a pointer to the sidecar. **Approval is per bucket** — that is what
keeps the queue reviewable at six thousand rows.

Extra bullets, kebab-short: `- signal:` (HubSpot `linkedin_message_signal`
verbatim) · `- channel: Connection Request` · `- linkedin: <url>` ·
`- note: "<invite text>"` · `- checked:` · `- crm: PROPOSE <update>`. Every card
and chat summary ends with:

`Reply draft these when you want me to prepare actions.`

## Exit codes

`ingest.py` and `act.py` share one table, so a scheduled job can branch on it.

| Code | Meaning | Typical cause |
|---|---|---|
| 0 | success | — |
| 2 | usage error | batch names nobody; unknown action |
| 3 | nothing to work on | no graded CSV; missing batch file |
| 4 | unreachable | signed out, or no browser on any rung |
| 5 | upstream | LinkedIn returned something unusable; webhook delivery failed |
| 6 | **refused by policy** | daily cap spent; `never_auto` without the named-list flag |
| 7 | rate limited | back off, retry later |
| 10 | config error | unknown `--profile`; unreadable `ernest.yaml` |

Every command answers in a provenance envelope —
`{"meta": {"source", "rung", "synced_at", "reason"}, "results": {...}}` — so a
caller can always tell live from cached from partial without guessing. `--agent`
implies `--json --compact` and never prompts. `--deliver stdout|file:<path>|webhook:<url>`.
`--profile <name>` saves a flag set for the scheduled run.

## Edge cases

| Case | Behavior |
|---|---|
| Premium "Follows you" card | Accept renders as an `<a>`; no click method fires it. Route to Ignore or surface for a manual click. **Never counted as accepted.** |
| "Take care when connecting" modal | Intermittent interstitial; click its *Accept invite*. A native dialog blocks page JS entirely — dismiss via `Page.handleJavaScriptDialog`. |
| Scrolling for more cards | Does nothing. ~10 mount per load; re-navigate. A stall counter stops the loop rather than spinning. |
| Person withdrew between grade and execute | Audited `MISSING`, not counted, not retried. |
| Same human under slug and URN | Collapsed by `identity_key`. |
| Zero Accept controls found | Ambiguous between empty queue and signed-out. The adapter **raises** rather than guess. |
| Archive requested without Invitations ticked | Parser raises naming the cause; the ladder falls to the next rung. |
| Engagement counts like "Name and 28 others" | Emit blank, not 0 — a numeric regex silently reads that as zero. |
| Queue older than 14 days | `ernest doctor` marks `data.linkedin` UNVERIFIED; the card still shows its real `source:`. |
| Rubric key deleted by hand | JSON replaces defaults wholesale — that family goes silent. `ernest doctor` names the missing key; `ernest heal` restores. |
| Cap spent mid-batch | Stops at the cap, exit 6, remainder left for tomorrow. Nothing partial is reported as complete. |
| Press or competitor scores 90 on ICP | Still `hold`. The order guarantees it. |

## Failure modes

- **Stale snapshot read as live** — check `source:` and the `at` stamp in
  `data/linkedin/.ingest.json`. Never present rung 2 or 4 as current.
- **Silent logged-out session** — zero Accept controls looks identical to an
  empty queue. If a card shows `items: 0` with `source: linkedin-live`, distrust
  it and run `ingest.py --doctor`.
- **Over-trashing** — the expensive one; reporting a real customer as spam cannot
  be undone. Sample 20 rows from the spam bucket against the CRM before the first
  approved batch and after any rubric change.
- **Approval fatigue** — a card past ~15 named items stops being read. Growing
  buckets with no approvals means the cadence is wrong, not the scoring.
- **Loop theater** — if `ernest learn` produces no actionable LinkedIn proposal
  for four straight weeks while overrides keep happening, the capture is broken.
  Rework the loop rather than keep emitting reports that change nothing.

## Verification

Transcribed from a real sandbox run:

```bash
export ERNEST_PROFILE_DIR=$(mktemp -d)/p ERNEST_LOCAL_VAULT=$(mktemp -d)/v \
       ERNEST_MODE=local ERNEST_TODAY=2026-08-24 PYTHONPATH=$PWD
mkdir -p $ERNEST_PROFILE_DIR && cp -R data memory ernest.yaml $ERNEST_PROFILE_DIR/
python3 adapters/linkedin/ingest.py --doctor
python3 -m ernest.cli grade --linkedin
```

`--doctor` prints `drivers: ['ego']` / `rungs reachable: [1, 2, 3]`. Grading then
writes `00-Watch/linkedin-invitations--2026-08-24.md` and its `.csv`:

```markdown
type: reminder-card
source: local-export
items: 7 (population 11; hold: 3, tier-1: 2, tier-2: 4, trash: 2)

## 1. [TIER-1] Tomas B. Enders - Halden Studios
- tier: tier-1 (confidence: high, match score: 87)
- signal: Positive
- action: Accept

## 3. [HOLD] Sasha Vance
- signal: Do Not Contact
- why: Competitor: 'novaframe'
- action: Hold — do not accept unread

## 6. [BUCKET] Spam / seller pitch (2)
- action: Say "remove the spam" to queue Ignore in batches. Nothing happens until you do.
```

The order, live: a production studio asking about an enterprise plan scores 87
and is proposed for Accept, while a competitor product lead with 15 mutual
connections is held as `Do Not Contact` — **suppression and hold ran before
scoring, so the mutuals never got a chance to promote them.** If a competitor
ever shows a tier instead of `hold`, the branch order changed; re-read
`grade_linkedin_inbound` before trusting any card.

Then the refusals, which are the actual product:

```bash
python3 adapters/linkedin/act.py --plan --tier trash --from-csv <the .csv>
#   Planned 2 × ignore (tier trash). Batch: .../00-Drafts/linkedin-ignore--2026-08-24.json
python3 adapters/linkedin/act.py --execute <batch>
#   Would perform 2 × ignore. (dry run — set dry_run=false and approved=true to act for real)
```

Engine optional: with no `data/linkedin/` the skill reports the ladder's honest
failure and its remedy, not an empty queue.

Run the guarantees: `python3 tests/test_linkedin_grading.py`,
`tests/test_linkedin_ingest.py`, `tests/test_linkedin_actions.py`.
