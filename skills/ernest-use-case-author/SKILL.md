---
name: ernest-use-case-author
description: Use when the CEO wants a new automation, a recurring manual pattern appears, or an existing skill needs improvement. Produces reviewable skill/config proposals only.
version: 1.1.0
---

# Ernest Use-Case Author

Turn repeated work, corrections, and outcomes into governed automations.

## Process

1. Check `ernest-library-index`.
2. If an existing skill fits, configure it by updating standing concerns or parameters.
3. If no skill fits, interview the CEO briefly:
   - What triggers this?
   - What sources/tools are needed?
   - What should happen?
   - What must never happen?
   - What output should Ernest produce?
   - Does it run on schedule, on demand, or both?
4. Produce a reviewable proposal. Do not silently apply it.
5. If approved, scaffold a new `skills/<name>/SKILL.md` using the template below.
6. Add a dry-run test/checklist and rollback.

## Governance

- Never auto-adopt external-send permissions.
- Never add credentials or connectors without CEO approval.
- Never expand memory scope.
- Prefer watch-first / draft-on-ask.
- Score against the north-star: friction and outcome.

## Proposal Format

```yaml
improvement_proposal:
  observed_pattern:
  change_type: configure_existing | new_skill | patch_skill | schedule | memory
  target:
  north_star_delta:
    friction:
    outcome:
  tools_needed:
  risks:
  approval_level:
  dry_run:
  rollback:
  status: proposed
```

## New Skill Template (the house shape — deep by construction)

Every section below exists for a reason; fill them all, delete none. `ernest
new-automation` scaffolds this same shape (`ernest/automations.py`), and the
contract test checks required sections.

```markdown
---
name: <skill-name>
description: <when to use — the always-loaded trigger surface, <=2 lines>
version: 0.1.0
---

# <Title>

## When to use
<trigger phrases + when NOT to use this skill>

## Parameters
<each param: default + WHERE IT LIVES (concern in memory/standing-concerns.md)>

## Data sources (read-only; swappable)
<per row: VPS brain tool -> local MCP -> data/ path; engine baseline command>

## Watch half
<numbered steps: search wide -> cross-check for resolution -> suppress handled
-> write ONE canonical card (see ernest-watch)>

## Decision criteria
<the actual thresholds, ranking keys, tie-breaks — never "use judgment" alone;
plus a tuning table: | Symptom | Diagnosis | Knob | Where it lives |>

## Draft half (explicit ask only)
<grounding (read-thread), voice source (ceo-persona), output 00-Drafts
STATUS: DRAFT, approval level L2/L3 named>

## Output
<canonical card ref + skill-specific extra bullets + the standard reply line>

## Failure modes
<what silently breaks and how it's detected (doctor check ids where relevant)>

## Verification
<exact command(s) + expected observable output, transcribed from a real run>
```

## Done-When

The result is either:

- a configuration proposal for an existing skill, or
- a new/modified `SKILL.md` proposal with dry-run instructions and rollback.
