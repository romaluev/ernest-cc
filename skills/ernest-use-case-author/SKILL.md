---
name: ernest-use-case-author
description: Use when the CEO wants a new automation, a recurring manual pattern appears, or an existing skill needs improvement. Produces reviewable skill/config proposals only.
version: 1.0.0
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

## New Skill Template

```markdown
---
name: <skill-name>
description: <when to use>
version: 0.1.0
---

# <Title>

## Parameters

## Watch Half

## Draft Half

## Safety

## Output

## When Not To Use
```

## Done-When

The result is either:

- a configuration proposal for an existing skill, or
- a new/modified `SKILL.md` proposal with dry-run instructions and rollback.
