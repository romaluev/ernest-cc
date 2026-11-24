---
name: talent-sourcing-grading
description: Source and grade talent for your company's outreach (current focus pool set in config, e.g. ex-NovaLabs alumni) into Tier-1, Tier-2, Tier-3. Use when sourcing or qualifying candidates, reviewing LinkedIn/GitHub profiles, building a recruiting pipeline, or deciding who to reach out to. Cast a WIDE net first, then rank. Assign owners; never message a candidate without approval.
version: 1.2.0
---

# Talent Sourcing & Grading

Goal: surface **many** good candidates, then **rank** them so outreach effort
goes to the strongest first. Your company and the focus pool are config, not
hardcoded — read **`memory/company-core.md`** for the real company name and
**`memory/icp-talent.md`** / **`data/grading/talent-rubric.json`** for criteria.
(If memory still shows sample names like "Northwind", onboarding hasn't run —
ask the user their company + pool first.)

## 1. Cast a wide net FIRST (this is the fix for "too few / too narrow")

Don't search once with one phrase. Breadth before precision:

- **Expand the query**: for each role, generate variants — synonyms, abbreviations
  (Sr.↔Senior, ML↔machine learning, SWE↔software engineer), adjacent titles
  (e.g. "research scientist", "applied scientist", "ML lead", "founding engineer"),
  and adjacent companies (the rubric's Big Tech list is a *seed*, not a limit —
  include peers: DeepMind, Tesla, Scale AI, Databricks, Midjourney, Runway, etc.).
- **Search multiple sources** if connected (LinkedIn/Apollo/Clay via MCP, GitHub,
  the ATS), not just one. Offline: the `profile` column in `data/sourcing/targets.csv`.
- **Pull more than you need** (aim for 30–50 raw candidates per role), then let the
  grade rank them. A short list is usually a search problem, not a talent shortage.
- **Don't pre-filter to perfection.** Keep Tier-2 and even strong Tier-3 as
  *options to consider*, flagged — never silently drop someone for thin text.

## 2. Grade + RANK by match score

```bash
ernest grade --talent
```
Cards land in `00-Watch/talent-grades--<date>.md`, sorted **Tier first, then
match score** (strongest match leads each tier — not arbitrary/date order). Use
it to decide outreach order; surface the top of each tier.

### Decision criteria — the actual scoring model

Source of truth: `ernest/grading.py` (**code wins**; the contract test keeps this
table honest). Decision order, then score:

1. **Exclusions short-circuit**: current employee or investor of the company
   (`exclusions` lists) → **tier-3, high, 0** — regardless of pedigree.
2. **Tier-1 signals** (any one qualifies; score adds per DISTINCT hit):

   | Signal (list in talent-rubric.json) | Weight | Structural? |
   |---|---|---|
   | senior title (`senior_titles`) AND Big-Tech co (`big_tech`) | +16 once | yes |
   | `strong_tech_keywords` (ML, CV, phd, kaggle, …) | +12 each | yes |
   | `ai_media_models` (sora, comfyui, diffusion, …) | +12 each | yes |
   | commercial signal AND Tier-1 country | +14 once | no |

   Confidence: **high** with any structural hit, else **medium**. Every Tier-1
   gets the flag "confirm likely interested (judgment call)".
3. **Tier-2 signals** (a single one surfaces the person as an option, low
   confidence): big_tech alone +8 each · US-startup signal +5 · product/GTM +5 ·
   Tier-1 country alone +2 — and country alone is **never** a qualifying reason.
4. **Nothing found → tier-3, low, 0** with the flag "read the full profile —
   local text may be thin". Never silently drop.

**Worked example** (engine-true): "Maya Chen, Senior Engineer at DeepMind,
profile: diffusion models, comfyui workflows, united states" → senior@big-tech
(+16) + ai_media `comfyui`, `diffusion` (+12×2) = **40, tier-1, high**, flagged
for the interest judgment call. Abbreviations expand before matching
(Sr.→senior, ML→machine learning, SWE→software engineer, …) so "Sr. ML Eng"
scores like the spelled-out title.

**Config footgun:** the JSON **replaces** code defaults wholesale — deleting a
key (e.g. `exclusions`) silently disables that family. Edit lists, never delete
keys; `ernest doctor` flags missing keys.

| Symptom | Diagnosis | Knob | Where it lives |
|---|---|---|---|
| Too few candidates surfaced | search too narrow, not a talent shortage | widen queries (§1) + broaden `big_tech`/`ai_media_models` | `data/grading/talent-rubric.json` |
| Wrong people at the top | thin `profile`/`title` columns | enrich the CSV row (grading reads them) | `data/sourcing/targets.csv` |
| Current teammate keeps appearing | exclusions list stale | add name/company to `exclusions` | rubric JSON |
| Pool changed (new focus) | snapshot rot | set `pool` + swap lists, re-run grade | rubric JSON + `memory/icp-talent.md` |

## 3. Hard filter + judgment

A candidate is a target only if **likely interested in the company** AND **not a
current employee/investor of the company**. Current employee/investor → Tier-3
for sourcing regardless of pedigree. "Likely interested" is **always** a flagged
judgment call — base it on trajectory; never assert what you can't ground.

## Output (per candidate)

```yaml
candidate:
  who: "<name>"
  tier: tier-1 | tier-2 | tier-3
  score: <match score>            # for ranking within a tier
  confidence: high | medium | low
  why: "<decisive signals>"
  likely_interested: yes | no | unknown
  excluded: false | "current employee/investor"
  action: "Tier-1/2 -> assign owner + warm outreach; Tier-3 -> hold/skip"
  source: "<profile url / ATS record>"
```

## Changing the criteria (it's a snapshot)

The pool and all signal lists are **living config** in
`data/grading/talent-rubric.json`. When the user says "change our talent focus"
or "add X as a Tier-1 signal", edit that JSON (`pool` + lists), summarize the
diff, and re-run `ernest grade --talent`. Broaden the lists freely — wider lists =
more candidates surfaced. Never hardcode the pool or company in logic.

## Verification (engine optional — sample data)

`ERNEST_TODAY=2026-06-25 ernest grade --talent` on the shipped samples: the card
sorts tier-1 first with per-candidate `match score`, and the sourcing rows with
`purpose=hire` are auto-tiered the same way in `partnership-sourcing` cards.
Spot-check one reason line against the weights table above — if they disagree,
code or rubric changed; re-read both.

## Hard rules

- A Tier-1 **country** alone is not a qualifier — it only strengthens "strong
  B2B/B2C experience in a Tier-1 country."
- Read the profile before discarding; thin local text → flag, don't trash.
- Never contact a candidate without the owner's approval.
- Tier corrections are learning signals: `ernest feedback "<name> was actually
  tier-1"`; recurring corrections feed `ernest learn` proposals.
