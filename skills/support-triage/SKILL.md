---
name: support-triage
description: Triage inbound support into needs-human-now / routeable / self-serve, ranked by SLA risk and requester tier. Use for support load, tickets, escalations, "what's on fire in support", response-time risk, or a deflection view — reads tickets; every reply and status change stays draft-first.
version: 1.1.0
---

# Support Triage

Northwind runs support on Pylon + Zendesk and is piloting Intercom Fin for
self-serve. There is no self-serve routing flow yet — this skill triages load,
proposes routes, drafts replies on ask, and flags what Fin/docs could deflect.
Its centerpiece is an explicit boundary: the list of things support automation
must NEVER answer alone.

## When to use

- "What's on fire in support?", queue health, escalation checks, SLA/response-time
  risk, "what could we deflect?", the support slice of a morning brief.
- NOT for: a live security incident (that escalates straight to the CEO/security
  owner — triage only records it), drafting one already-known reply (just ask for
  the draft), or authoring help docs (doc gaps leave here as proposals).

## Inputs

```yaml
scope: "open"            # open | breaching-sla | escalations | last_24h
queue: "*"               # pylon | zendesk | *
sla_horizon: "4h"        # needs-human when sla_due - now < this
repeat_threshold: 3      # same question >= Nx in window -> self-serve candidate
window: "7d"             # repeat-counting window
```

Defaults live here; if the CEO schedules this as a standing concern, overrides
live in `memory/standing-concerns.md` (change by talking to Ernest — never
hand-edit YAML).

## Data sources (read-only; swappable)

Connectors are a layer, not a hardcode — repoint rows at whatever the company
runs. Use the first available per row; label exports `source: local-export`.

| Need | VPS brain -> local MCP | Export fallback |
|---|---|---|
| Tickets: status, priority, age_hours, sla_due, requester, last_reply_by | (no brain ticket tool yet) -> Pylon + Zendesk MCP | `data/support/tickets.csv` |
| Requester tier (canonical) | `mcp__ernest-brain__search_hubspot` -> HubSpot MCP | `data/hubspot/sample-contacts.csv` |
| Already-handled cross-check, front-door threads | `mcp__ernest-brain__search_slack` / `search_mail` -> Slack + Gmail MCP | `data/slack/**`, `data/mail/**` |
| Help/policy docs (answers + gap detection) | Notion MCP | `data/notion/**` |
| What Fin already deflects | Intercom (Fin) MCP when connected | — (state that it's missing) |

Engine baseline: none — this is a model-run connector skill; tier lookups call
`ernest.grading` (see Verification). No connector and no export? Say what's
missing and offer a demo on `data/support/tickets.csv` — never fake a workflow.

## Watch half

1. **Search wide**: pull tickets in `scope` from every connected queue, plus
   Slack front-door threads that never became tickets.
2. **Grade requesters**: company tier via `b2b-lead-grading` (CRM canonical;
   not-in-CRM grades tier-2/low — that is a confidence flag, not a downgrade).
3. **Cross-check for resolution** before flagging: already handled in Slack or
   mail, or answered by Fin? Suppress handled items; if the ticket tool is
   stale, keep one line — "resolved elsewhere, propose status update" (proposal
   only, never applied).
4. **Bucket and rank** using Decision criteria below.
5. Write ONE canonical reminder card (`ernest-watch` format) to
   `00-Watch/support-triage--<date>.md`. No reply text in watch mode.

## Decision criteria

Evaluate in this order; the first match sets the bucket.

**1. needs-human-NOW** — any ONE trigger is enough:

- **SLA**: `sla_due − now < sla_horizon` (default 4h). Parse `sla_due` as UTC;
  a missing or unparseable `sla_due` counts as breaching — never silently skip.
- **Tier-1 requester**: the requester's company grades tier-1 via
  `b2b-lead-grading` (HubSpot/CRM tier is canonical and wins).
- **Mandatory-human-review list** — subject/body hits any item below. This is
  the boundary: support automation must NEVER answer these alone, however
  confident the suggested reply looks.
  1. refund or billing dispute
  2. legal / DPA / contract-terms question
  3. security incident, breach, or SSO/auth failure
  4. churn or cancellation threat
  5. pricing commitment or discount ask
  6. press / media inquiry
  7. regulator mention (data-protection authority, central bank, …)
  8. data deletion request
  9. exec escalation ("CEO", "urgent from <name>")
  10. anything implying money movement (payouts, chargebacks, wire details)
  11. complaint about a human (agent or teammate)
  12. safety or abuse report

**2. routeable** — a real issue with none of the triggers → propose the queue
owner with a one-line summary (assignment proposal; never auto-reassign).

**3. self-serve candidate** — the SAME question ≥ `repeat_threshold` (3x) in
`window` AND an existing doc/macro answers it → propose the doc-link reply
(draft, L2). If NO doc exists → that is a **DOC GAP** finding (propose writing
the doc; flag it as a Fin deflection candidate) — not a self-serve. Cluster by
normalized question meaning, not exact subject string.

**Ranking** (inside each bucket): SLA risk — soonest `sla_due` first → requester
tier (tier-1 first) → `age_hours` (oldest first).

| Symptom | Diagnosis | Knob | Where it lives |
|---|---|---|---|
| Humans pinged for everything | horizon too wide | `sla_horizon` (4h) | `## Inputs` here (+ concern override) |
| Breach found after the fact | horizon too narrow, or stale `sla_due` | same knob; check export freshness | same |
| Obvious FAQ never deflected | threshold too high / clustering too literal | `repeat_threshold` (3); normalize questions | this file |
| Sensitive ticket landed "routeable" | review list missing a phrasing | add the phrasing to the list | **this SKILL.md is the review list's home**; log misses with `ernest feedback` so `ernest learn` proposes the diff |
| Tier-1 customer ranked low | company missing or stale in CRM | fix the HubSpot tier (propose, draft-first) | HubSpot + `data/grading/b2b-rubric.json` |

## Draft half (explicit ask only)

Runs only on "draft these" or a direct CEO instruction.

1. Ground every draft in the FULL ticket thread (read every message) plus the
   Notion doc/policy it relies on, and cite that doc in the draft. Missing doc =
   say so; never improvise policy.
2. Reply drafts only → `00-Drafts/`, `STATUS: DRAFT`, approval **L2**. Never
   send. Never change status/assignee/SLA — those are proposals (L2).
3. **The boundary holds inside drafts too**: a draft for a review-list ticket
   may acknowledge, state verified facts, and promise a named human will follow
   up — it must never confirm a refund or credit, agree to or interpret
   legal/contract terms, commit pricing or discounts, or confirm data deletion.
   Money and legal are **L3**: manual only.
4. Prefer deflection: every repeated question ships with its doc-gap proposal.

## Output

One canonical reminder card per run (`ernest-watch` format — that skill defines
the card; do not restyle it). Skill-specific extra bullets, kebab-short:
`- ticket: T-1042 (pylon)` · `- sla: 2026-06-25T10:00Z (2h left)` ·
`- bucket: needs-human | routeable | self-serve` ·
`- checked: tickets,slack,mail,hubspot` · `- crm: PROPOSE <tier fix>`.

Chat stays house-format: **Bottom line** (biggest SLA/customer risk right now),
the needs-you list (who · action · why now · ticket), **Read more →** the
rendered queue view. Every card and summary ends with:

`Reply draft these when you want me to prepare actions.`

## Failure modes

- **No ticket connector** → fall back to `data/support/tickets.csv`; if that is
  missing too, say so. `ernest doctor` covers connectors (`connectors.mcp`);
  support exports have no dedicated check — verify the file exists by hand.
- **Stale exports / stale `sla_due`** → SLA math silently wrong. State export
  age on the card; treat missing `sla_due` as breaching.
- **Requester not in CRM** → grades tier-2/low/2 (engine-verified default) —
  flag low confidence instead of quietly ranking a real customer low.
- **Literal keyword matching** → "charge me twice" slips past a "refund" rule;
  match meaning, and log misses (`ernest feedback` → `ernest learn`).
- **Resolved in Slack, open in the tool** → skipping Watch step 3 makes the
  card cry wolf; suppress and propose the status update instead.

## Verification

Fixture: `data/support/tickets.csv` (8 open tickets); reference time
2026-06-25T08:00Z. The tier claim is engine-true — transcribed from a real run:

```bash
$ PYTHONPATH=. python3 -c "from ernest import config; from ernest.grading import grade_b2b; \
g=grade_b2b(company='Apex Bank', crm_tier='vip', cfg=config.load()); \
print(g.tier, g.confidence, g.reasons, int(g.score))"
tier-1 high ["CRM tier 'vip' -> tier-1"] 100
```

(`vip` comes from `data/hubspot/sample-contacts.csv`. Brightline Creative and
Meridian Media have no CRM row and grade tier-2/low/2 — also run-verified — so
neither is a tier-1 trigger.)

Expected triage of the fixture:

- **needs-human-NOW**: `T-1042` first (all three triggers at once: sla_due
  10:00Z = 2h out; Apex Bank tier-1; "refund" = billing dispute, item 1) →
  `T-1045` (SSO/auth failure = security, item 3; sla 16:00Z) → `T-1048`
  (legal/DPA, item 2, plus Apex Bank tier-1; sla 18:00Z). Order: soonest
  sla_due first.
- **routeable**: `T-1041` (render quota, high; sla 14:00Z = 6h out — outside
  the 4h horizon; it flips to needs-human after 10:00Z — the `sla_horizon` knob
  working).
- **self-serve candidate**: `T-1043` + `T-1044` + `T-1046` — "How do I export
  in 4K?" 3x meets `repeat_threshold` → ONE cluster; doc exists → doc-link
  reply proposal (L2); no doc → DOC GAP.
- `T-1047` (feature request, low, 70h, latest sla_due 2026-06-28T12:00Z) sorts
  **last** in every view.

Different buckets on your run? Re-read the review list and the CRM tiers before
trusting the triage.
