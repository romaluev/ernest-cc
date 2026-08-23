# LinkedIn inbound rubric — where each piece lives

Three files, and they are not interchangeable:

| Piece | Lives in | Change it by |
|---|---|---|
| Decision **order** and the weights | `ernest/grading.py` (`grade_linkedin_inbound`, `LINKEDIN_WEIGHTS`, `LINKEDIN_SPAM_WEIGHTS`, `SPAM_THRESHOLD`) | editing code + a test |
| The signal **lists** | `data/grading/linkedin-rubric.json` | editing the JSON |
| What the tiers **mean** for the CEO | `memory/icp-b2b.md` | talking to Ernest |

`tests/test_linkedin_grading.py` keeps this page honest against the code.

## Decision order (the safety mechanism)

```
1. suppression   HubSpot list membership       -> hold / accept / drop
2. hold          press, legal, competitor,     -> hold, never auto-resolved
                 investor, exec reference
3. CRM tier      a known relationship          -> that tier, confidence high
4. tier-1        ICP signals, scored by density
5. job seeker    a lane of its own             -> tier-2, signal JOB_SEEKER
6. spam          scored, needs >= threshold    -> trash
7. default       tier-2, low, flagged
```

Checking tier before suppression is how a competitor or a journalist ends up
accepted and then sequenced. This order is not a style choice.

## Tier-1 weights (per DISTINCT list hit — density, so two signals beat one)

| Signal | Rubric list | Weight |
|---|---|---|
| Buyer archetype | `tier1.buyer_archetypes` | +14 each |
| Platform / API buyer | `tier1.platform_buyers` | +14 each |
| Won-revenue vertical | `tier1.verticals` | +10 each |
| Model/cloud provider | `tier1.providers` | +12 each |
| Major company | `tier1.companies` | +12 each |
| Decision-maker title | `tier1.seniority_keywords` | +8 each |
| Buying intent in the note | `tier1.intent_keywords` | +10 each |
| Relevant function | `tier1.function_keywords` | +4 each |
| CEO reference **or** CRM prior contact | — | +16 once |
| Mutuals at or above the floor | `tier1.min_mutual_connections_signal` | +6 once |
| A country we actually close in | `tier1.tier1_countries` | +3 once |

**Tier-1 needs a *who*.** A title, a country, and mutual connections alone never
qualify — the sender must hit an archetype, vertical, platform, provider, or
company. Seniority and intent then decide `high` vs `medium` confidence, and a
score of 24+ qualifies on structure alone.

CRM tier short-circuits everything below it: score 100 for tier-1, 60 otherwise.

## Spam weights (threshold **5.0**)

| Evidence | Rubric list | Weight |
|---|---|---|
| Cold-vendor phrase | `spam.vendor_keywords` | +4 each |
| Spam-headline pattern | `spam.headline_keywords` | +3 each |
| Mass-template fingerprint | `spam.template_fingerprints` | +2 each |
| Thin network | `spam.low_connection_threshold` (50) | +2 |
| Zero mutual connections | — | +1.5 |
| No note at all on a cold invite | — | +0.5 |

Below 5.0 the evidence is reported as a `- check:` flag and the invitation stays
tier-2. One template phrase is not proof of anything — plenty of real people
write "I'd love to connect".

**Missing is not zero.** A blank mutual count means "we did not look" and scores
nothing; only a real `0` is evidence. The archive rung carries neither count, so
an archive-sourced population under-detects spam by design. That is the correct
trade: under-detecting spam costs a scroll, over-detecting it costs a customer.

## Signals (HubSpot `linkedin_message_signal`, verbatim)

`Positive` · `Negative` · `Seller Pitch` · `JOB_SEEKER` · `Do Not Contact` ·
`Spam` · `None`. The portal already models this surface — emit its vocabulary,
do not invent a parallel one. Same for
`linkedin_inbound_invitation_status` (`Pending | Accepted | No Longer Pending`)
and `linkedin_qualification_channel` (`Inbox | Engagement | Connection Request`).

## Config footgun

The JSON **replaces** code defaults wholesale. Deleting a key — say `spam` —
silently turns that whole signal family off and everything starts grading
tier-2/low with no error. **Edit lists, never delete keys.** `ernest doctor`
checks the file parses and carries its top-level keys.

## Teaching it

`ernest feedback "<who> was actually <tier>"`. At three independent signals of
the same shape, the improve loop proposes a rubric diff with its reverse, which
you adopt with `ernest learn --apply <key>` and undo with `--rollback <id>`.
Nothing edits the rubric silently — `sync.yaml` pins `max_auto_changes_per_run: 0`.
