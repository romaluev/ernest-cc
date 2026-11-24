# B2B Tier Rubric — where each piece lives (no duplication)

- **Tier policy** (what Tier-1/2/Trash MEAN for this company): `memory/icp-b2b.md`
  — the living, CEO-editable definition.
- **Scoring mechanism** (decision order, weights table, worked example, tuning
  knobs): `SKILL.md` §"Decision criteria" in this skill — kept honest against
  `ernest/grading.py` by the contract test.
- **Signal lists + thresholds** (the actual names/keywords/AUM threshold):
  `data/grading/b2b-rubric.json` — living config; the JSON *replaces* code
  defaults wholesale, so edit lists, never delete keys.

One rule to remember: CRM > curated lists > inference, and inference is always
flagged.
