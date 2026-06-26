---
name: talent-sourcing-grading
description: Grade talent for Higgsfield outreach (current focus pool: ex-Skolkovo alumni) into Tier-1, Tier-2, or Tier-3/Trash. Use when sourcing or qualifying candidates, reviewing LinkedIn profiles, building a recruiting pipeline, or deciding who to reach out to. Assign owners; never message a candidate without approval.
version: 1.0.0
---

# Talent Sourcing Grading

Grade candidates so outreach effort goes to Tier-1 first. Current pool focus:
**ex-Skolkovo** alumni. Full criteria: `memory/icp-talent.md`. Quick rubric:
`references/rubric.md`.

## Hard filter first (applies to everyone)

A candidate is only a target if they are **likely interested in Higgsfield**
AND **not a current Higgsfield investor or employee**. Current investor/employee
→ not a sourcing target (Tier-3 for sourcing), regardless of pedigree.

## Signal priority

1. **ATS/CRM** if connected (stage, prior contact, owner).
2. **Curated lists** — `data/grading/talent-rubric.json` (Big Tech, AI media
   models, Tier-1 countries, senior titles, commercial signals).
3. **Inference** from the profile. "Likely interested" is **always** a flagged
   judgment call — base it on trajectory, never assert what you can't ground.

## Run sequence

1. Read the candidate's full profile/career history (live: read profile via MCP;
   offline: the `profile` column in `data/sourcing/targets.csv`).
2. Get the deterministic starting grade:
   ```bash
   ernest grade --talent
   ```
   Cards land in `00-Watch/talent-grades--<date>.md`, sorted Tier-1 first.
3. Apply the hard filter, then resolve `check:` flags (interest, exclusions).
4. Assign an outreach owner for Tier-1/2. Tier-3 = skip.

## Output (per candidate)

```yaml
candidate:
  who: "<name>"
  tier: tier-1 | tier-2 | tier-3
  confidence: high | medium | low
  why: "<decisive signals>"
  likely_interested: yes | no | unknown   # judgment — explain briefly
  excluded: false | "current Higgsfield investor/employee"
  action: "Tier-1/2 -> assign owner + warm outreach; Tier-3 -> skip"
  source: "<profile url / ATS record>"
```

## Changing the criteria (it's a snapshot)

The pool (currently ex-Skolkovo) and all signal lists are **living config** in
`data/grading/talent-rubric.json`. When Alex says "change our talent focus" or
"add X as a Tier-1 signal", edit that JSON (`pool` + lists), summarize the diff,
and re-run `ernest grade --talent`. Never hardcode the pool in logic.

## Hard rules

- A Tier-1 **country** alone is not a qualifier — it only strengthens "strong
  B2B/B2C experience in a Tier-1 country."
- Read the profile before discarding; local text may be thin (don't trash on
  missing data — flag it).
- Never contact a candidate without Alex/owner approval.
