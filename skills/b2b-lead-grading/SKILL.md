---
name: b2b-lead-grading
description: Grade and sort inbound B2B leads/threads into Tier-1, Tier-2, or Trash so the CEO only sees what matters. Use when triaging inbound, deciding who to reply to first, qualifying a prospect, or asking "is this worth my time?". Be generous on real fit, strict on trash; rank by match strength. Remind/assign only; never auto-reply.
version: 1.2.0
---

# B2B Lead Grading

Sort inbound so the CEO spends reply time on Tier-1, Tier-2 is routed, and trash
never reaches them. Company + ICP are config, not hardcoded — read
**`memory/company-core.md`** for the real company and **`memory/icp-b2b.md`** /
**`data/grading/b2b-rubric.json`** for criteria. (Sample names like "Northwind"
mean onboarding hasn't run — ask the user their company + ICP first.)

## Signal priority (always in this order)

1. **CRM** — existing tier, deal stage, or prior activity wins.
2. **Curated lists** — `data/grading/b2b-rubric.json`.
3. **Inference** — content + public knowledge. Can't confirm a Tier-1 claim
   (e.g. market-leader)? **Flag low confidence**; don't guess.

## Decision criteria — the actual scoring model

Source of truth: `ernest/grading.py` (**code wins**; the contract test keeps this
table honest). Decision order, then score:

1. **CRM tier present → done.** `crm_tier_map` (vip/enterprise/investor/strategic
   → tier-1; partner/smb → tier-2), confidence high, score 100 (tier-1) / 60.
2. **Any Tier-1 signal → tier-1.** Score adds per DISTINCT list hit (density —
   two signals beat one):

   | Signal (list in b2b-rubric.json) | Weight |
   |---|---|
   | `tier1.categories` (ai studio, ad agency, …) | +8 each |
   | `tier1.providers` (openai, aws, nvidia, …) | +12 each |
   | `tier1.companies` (google, wpp, coca-cola, …) | +12 each |
   | `tier1.people` (named high-reputation people) | +15 each |
   | `tier1.intent_keywords` (procurement, msa, rfp, …) | +6 each |
   | CEO reference OR CRM prior contact (either) | +14 once |
   | Fund with AUM > `fund_aum_threshold_busd` ($2B) | +15 |

   Confidence: **high** if any structural hit (category/provider/company/person/
   reputation/prior/fund); **medium** if intent keywords only.
3. **Trash signals** (only when no Tier-1 hit): `trash.vendor_keywords`
   ("we offer", backlink, seo services…) → trash/medium/0. Small-media words →
   trash/low with the flag "confirm <~100k readers, else Tier-2 media".
4. **Nothing decisive → tier-2, low, score 2** + a verify flag. Never silent
   Tier-1, never silent trash.

Sort order everywhere: `(tier rank, −score, −days waiting)`.

**Worked example** (run it: these are engine-true): text "we are an ai studio
planning an enterprise rollout, procurement started" → categories `ai studio`,
`enterprise` (+8×2) + intents `enterprise`, `procurement`, `rollout` (+6×3) =
**34, tier-1, high**. A $6B fund with no other signal = **15, tier-1, high**.
The sample vendor pitch ("We offer SEO services + backlinks") = **0, trash**.

**Config footgun:** the JSON **replaces** code defaults wholesale — deleting a
key (e.g. `trash`) silently turns that whole signal family OFF. Edit lists,
never delete keys; `ernest doctor` flags missing keys as UNVERIFIED.

| Symptom | Diagnosis | Knob | Where it lives |
|---|---|---|---|
| Real buyer graded tier-2 | list too narrow | add company/category | `data/grading/b2b-rubric.json` (or 3× `ernest feedback "X was actually tier-1"` → `ernest learn` proposes the diff) |
| Vendor spam reaching Tier-2 | vendor phrasing not listed | add to `trash.vendor_keywords` | same file |
| Everything Tier-1 | lists too broad / CRM tiers stale | prune lists; fix CRM tiers | rubric + HubSpot |
| Wrong order inside a tier | score too flat | weights | `ernest/grading.py` (engine change — propose, don't hand-edit) |

## Grade widely, rank by score

- The rubric lists are a **seed, not a limit.** Recognize ICP fit beyond the
  literal list: a small-but-famous AI studio, a known agency, a real enterprise
  buyer, or genuine enterprise intent all count even if not listed — use public
  knowledge and note it (that's the inference tier: flag it).
- **Don't over-trash.** Only obvious cold vendor/SEO/backlink pitches are trash.
  An ambiguous lead is Tier-2 with a flag, not trash — surface it.

```bash
ernest grade --b2b
```
Cards land in `00-Watch/b2b-grades--<date>.md`, sorted Tier-1 first, each with
reasons, a match score, and `check:` flags. Read the full thread (`read-thread`)
before finalizing — grade on what they said, not a subject line.

## Output (per lead)

```yaml
lead:
  who: "<name> — <company>"
  tier: tier-1 | tier-2 | trash
  score: <match score>
  confidence: high | medium | low
  why: "<decisive signals>"
  action: "Tier-1 -> CEO replies; Tier-2 -> route to owner; Trash -> archive/decline"
  source: "<thread_id / CRM record>"
```

## Verification (engine optional — sample data)

`ERNEST_TODAY=2026-06-25 ernest grade --b2b` on the shipped samples: the card
shows `items: 11 (tier-1: 3, tier-2: 7, trash: 1)`; Apex Bank leads with
`CRM tier 'vip' -> tier-1 … match score: 100`; the GrowthHooks vendor pitch is
`[TRASH] … Cold vendor pitch: 'we offer'`. If your numbers differ, the rubric
JSON or code changed — re-read both before trusting grades.

## Hard rules

- Remind/assign only. Drafts happen only on the CEO's explicit "draft these".
- Conflicting signals → take the **higher** tier and note the conflict.
- A strategic-but-small account that fits the ICP is Tier-1 on fit, not size.
- Trash is a recommendation to archive/decline — never an auto-send.
- Tier corrections are learning signals: log them (`ernest feedback "<who> was
  actually <tier>"`); at 3× the improvement loop proposes the rubric diff.
