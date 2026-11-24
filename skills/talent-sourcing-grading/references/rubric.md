# Talent Tier Rubric — where each piece lives (no duplication)

- **Tier policy + hard filter** (what Tier-1/2/3 MEAN; likely-interested AND
  not-current-employee/investor): `memory/icp-talent.md` — the living,
  CEO-editable definition. Pool focus is a snapshot (`pool` in the JSON).
- **Scoring mechanism** (decision order, weights table, worked example,
  abbreviation expansion, tuning knobs): `SKILL.md` §"Decision criteria" in this
  skill — kept honest against `ernest/grading.py` by the contract test.
- **Signal lists** (big_tech / senior_titles / ai_media_models / exclusions …):
  `data/grading/talent-rubric.json` — living config; the JSON *replaces* code
  defaults wholesale, so edit lists, never delete keys.

Two rules to remember: exclusions short-circuit to Tier-3 regardless of
pedigree, and a Tier-1 country alone is never a qualifier.
