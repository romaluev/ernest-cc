# LinkedIn triage — what gets checked, in what order, and why

The complete decision spec for both surfaces. If a report ever surprises you,
the answer is on this page.

Two sentences that explain most of the design:

1. **Order is the safety mechanism.** Checking "is this a good lead" before "is
   this a journalist" is how a reporter ends up in a sales sequence. The order
   below is not a style choice and is asserted by tests.
2. **Facts outrank inference, and unknown is neither.** A closed-won number is a
   fact. "Their headline says founder" is a guess. "We cannot tell who this is"
   is a third state that caps what they can influence — it never quietly
   averages into the middle.

---

## 1. Where the data comes from

An ingest ladder, because LinkedIn has no API we can use. Each rung reports
itself, and that label reaches the top of every report as `source:`.

| Rung | Source | Label | Carries |
|---|---|---|---|
| 1 | a fresh file already on disk | whatever wrote it | — |
| 2 | LinkedIn's own data export | `linkedin-archive` | invitations + **full message text**; no headline, no mutual counts |
| 3 | the live invitation-manager / messaging DOM | `linkedin-live` | everything, and the only rung that can act |
| 4 | HubSpot's `linkedin_*` properties | `hubspot-mirror` | a **subset** — only people already in the CRM |
| 5 | nothing worked | `unavailable` | nothing, and it says so |

Rung 5 writes no file and prints a remedy. **An empty queue and an unreachable
one are different answers**, and nothing here will collapse them.

Rung 2 under-detects spam by design: with no mutual-connection count, structural
evidence is thinner. That is the correct trade — missing spam costs a scroll,
wrongly reporting a customer cannot be undone.

Files are read from an **allow-list**, not a deny-list. A real export drops
`Invitations.csv`, `Connections.csv` and `messages.csv` in one folder, and
"skip the ones we thought of" once loaded messages as invitations.

---

## 2. Who is this, and what are they worth?

One value model, used by both surfaces and by every feature below.

**Facts** — verifiable, and weighted to dominate:

| Signal | Points |
|---|---|
| Open deal in the CRM | 45 |
| Closed-won revenue | up to 40, log-scaled (0→50k matters; 2M→4M does not) |
| CRM tier is tier-1 | 30 |
| CRM tier, other | 12 |
| Known contact with a real touch | 10 |

**Inference** — from what they wrote, an order of magnitude smaller:

| Signal | Points |
|---|---|
| Major company | 12 each |
| Buyer archetype / platform-API buyer | 10 each |
| Buying intent phrase | 9 each |
| Provider | 9 each |
| Vertical | 7 each |
| Decision-maker title | 7 |
| We have replied before | 12 |
| Each reply we sent | 3 (capped at 5) |
| Each message in the thread | 1.5 (capped at 8) |
| Mutual connections above the floor | 4 |

**Bands:** `critical` ≥75 · `high` ≥42 · `medium` ≥20 · `low` ≥8 · `noise` below.

**Unknown.** A name is not an identity. Without a company, a title, a CRM record,
or a conversation we took part in, the person is `unknown` and their band is
**capped at `low`** regardless of score — anyone can type "enterprise rollout"
into a cold message.

**But unknown ≠ ignore.** If an unidentified person states real commercial
intent, they are flagged **WORTH IDENTIFYING** and surfaced in their own section.
The next action there is a 30-second lookup, not a reply written in the dark.
Burying a real lead under a cap would be the same mistake in the other direction.

---

## 3. Invitations — the decision order

```
suppression → hold → CRM tier → tier-1 signals → job seeker → spam → default tier-2
```

| Step | Rule | Result |
|---|---|---|
| **Suppression** | HubSpot list `411` (the union — check first), `400` competitors, `412` investors, `413` press, `414` partners, `485` partner domains, `484` agency review | `hold`. List `399` (employees) → **Accept**; colleagues are not spam |
| **Hold** | press, legal/regulatory, competitors, investors, anyone claiming a prior conversation with the CEO | `hold`, never auto-resolved in either direction |
| **CRM tier** | a known relationship | that tier, confidence `high` |
| **Tier-1** | needs a **who**: buyer archetype, vertical, platform/API, provider, or major company | seniority, country and mutuals only amplify — a VP with no ICP hit is tier-2 |
| **Job seeker** | its own lane | tier-2, signal `JOB_SEEKER` |
| **Spam** | scored, see below | `trash` |
| **Default** | anything else | tier-2, low confidence, flagged |

### How spam is decided

Spam is **scored, never matched**. One template phrase is not proof — plenty of
real people write "I'd love to connect".

| Evidence | Points |
|---|---|
| Cold-vendor phrase | 4 each |
| Spam-headline pattern | 3 each |
| Mass-template fingerprint | 2 each |
| Thin network (< 50 connections) | 2 |
| Zero mutual connections | 1.5 |
| No note at all on a cold invite | 0.5 |

**Threshold: 5.0.** Below it, the evidence is reported as a `check:` flag and the
invitation stays tier-2. The threshold lives in the rubric JSON, not in code, so
it can be tuned from evidence.

**Missing is not zero.** A blank mutual-connection count means "we did not look"
and scores nothing. Only a real `0` counts.

**Two hard rules:** never a silent tier-1, never a silent trash. And do not
over-trash — an ambiguous stranger is tier-2 with a flag.

---

## 4. Direct messages — a different first question

An invitation asks *who is this*. A DM asks **am I the one holding this up**.

```
escalation → suppression → hold → replied-before → owed+ICP → job seeker → spam → FYI
```

| Step | Rule | Bucket |
|---|---|---|
| **Escalation** | money/billing, legal, security/data, churn, safety | `escalation` — answer personally |
| Suppression / Hold | same lists as invitations | `hold` |
| **Replied before** | we took part in this thread | can be low priority, **never spam** |
| Owed + ICP | they wrote last; archetype, intent, a question asked | `needs-reply` |
| Job seeker | its own lane | `fyi` |
| Spam | scored on the **opener** only | `trash` |
| Otherwise | nothing owed | `fyi` |

**Escalation runs before everything, including our own prior replies.** A refund
dispute from a long-standing customer is *more* urgent than one from a stranger,
not less.

**Spam is scored on the opener, not the whole thread.** Quoting a pitch back
while declining it must not make the thread read as the pitch. And spam never
applies to a thread we answered — a conversation we joined is a relationship.

**Direction is derived, not given.** The export has one row per message with
FROM/TO and no direction column, so the account owner is matched from
`memory/ceo-persona.md`, falling back to whoever appears in the most **distinct
threads** — not the most messages, since one persistent spammer can out-message
the owner inside a single thread. Getting this wrong inverts every message in
the inbox, so it is the highest-consequence step in the whole system.

---

## 5. What gets dug out of a thread

### Unkept commitments — promises *we* made

Structurally invisible to ordinary triage: they live in threads we already
replied to, so "owed" is false and they look like nothing to do.

Detected from outbound messages ("I'll…", "let me…", "happy to…"), while
excluding asks ("let me know if…"), then classified:

| Type | Weight |
|---|---|
| legal / payment | 1.6 |
| pricing | 1.4 |
| decision | 1.3 |
| scheduling | 1.2 |
| materials | 1.1 |
| intro | 0.9 |

`value = counterparty score × type weight`, ×1.8 if **they chased**, ×1.25 if
over 14 days old.

**Dropped, not shown:**

- already delivered (a later message of ours names it again, or reads as a delivery)
- **an intro with no named subject** — "I'll intro you to someone who can help"
  is a pleasantry; a human cannot act on it without asking a follow-up question
- an intro to a counterparty we cannot identify
- counterparty is `noise`
- stale: over 180 days, never chased, and the relationship is not strong
- below a value floor of 12

### Deadlines

Extracted from inbound messages and resolved **against the date the message was
written**, never against today — "by Friday" written in June means a Friday in
June. Phrases stop at the first clause break, so "by Friday, our board meets
before the 15th" is two deadlines rather than one wrong one.

### Thread state

Stage (`cold → engaged → scheduling → evaluating → negotiating → contracting →
closed`), who owes whom, days quiet, and the blocking item. Stage cues only
count as engagement **if we actually replied** — a one-line pitch containing the
word "question" is still a cold pitch. A closed thread owes nobody anything.

### Campaigns

Near-identical openers across different senders are **one judgment, not N**.
Clustered on 3-word shingles with Jaccard similarity, threshold **0.45**, minimum
3 members. Measured, not guessed: genuine messages score 0.00 against each other
while spintax variants of one blast sit at 0.40–1.00.

Clustering uses the **message only**, never the headline — a campaign varies its
personas' headlines on purpose, and mixing them dilutes the signal below
threshold exactly when it matters.

### One person, both surfaces

Someone who invited us *and* messaged us is one person with two open threads.
Keyed by profile slug, falling back to member URN (`ACoAA…`), falling back to a
normalized name — LinkedIn reports the same human both ways, and keying on
either alone double-counts them.

### What changed since last run

Each run stores its state, so the next report says what is new, what got more
urgent, what cleared, and what is still waiting after N days. A report identical
every morning stops being read.

---

## 6. Acting

Reading and acting are separate commands, always. Execution performs **only the
identity keys named in an approved batch** — "ignore all the spam" has to survive
being wrong about one person.

| Action | Reversible | Ceiling | Cap/day |
|---|---|---|---|
| Ignore invitation | yes — they can re-invite | L1 after clean runs | 100 |
| Accept invitation | yes — remove the connection | L1 after clean runs | 25 |
| Archive DM | yes — it returns on a new message | L1 after clean runs | 200 |
| Delete DM | **no** | **L2 forever** | 25 |
| Report as spam | **no**, and it affects their account | **L2 forever** | 25 |
| Reply / InMail | no | out of scope | — |

Never reachable by a batch, by any route: `hold`, `escalation`, and any DM still
owed a reply that is not already classified spam.

Caps are counted from the **audit log**, so a run that crashed halfway still
consumed what it used. Pacing between actions is a safety property, not
politeness — sudden mass action is what gets accounts restricted.

---

## 7. Learning

There is no evaluation set at this volume. But every proposal is kept or
overridden, so **override rate is an outcome measure with N = every decision**.

```
act.py --rescue <key> --actual <tier> --why "..."
```

Three overrides of the same shape produce a rubric diff with its reverse,
adopted with `ernest learn --apply` and undone with `--rollback`. Nothing edits
scoring silently — `max_auto_changes_per_run` is pinned at 0.

For that loop to have anything to turn, thresholds live in the rubric JSON, not
in code. A constant is not a knob.

---

## 8. Tuning

`data/grading/linkedin-rubric.json` is the whole scoring brain. Edit the lists:

| Key | What it decides |
|---|---|
| `tier1.buyer_archetypes`, `verticals` | who counts as a real buyer |
| `tier1.intent_keywords` | what buying intent sounds like |
| `hold.competitor_keywords` | who never gets accepted unread |
| `escalation.*` | what must reach a human |
| `spam.vendor_keywords`, `headline_keywords`, `template_fingerprints`, `dm_blast_keywords` | what cold outreach looks like |
| `spam.threshold` | how much evidence before Ignore is proposed |
| `suppression` | HubSpot list ids and their routing |

Derive the archetypes and verticals from **closed-won revenue**, not from a
targeting deck. The two disagree more often than not.

**Edit lists; never delete a key.** The JSON replaces built-in defaults
wholesale, so a missing key silently disables that entire signal family.
`ernest doctor` names any that go missing.
