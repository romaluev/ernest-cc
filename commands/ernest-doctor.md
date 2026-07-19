# /ernest-doctor

Use the `ernest-self-repair` skill. Diagnose Ernest and fix what's broken or
missing so the CEO doesn't have to.

Baseline — the four-state health audit:

```bash
ernest doctor            # human-readable table
ernest doctor --json     # machine-readable, for the repair skill to consume
```

Every subsystem reports one of four states: **WORKING** (verified good),
**UNVERIFIED** (configured but unproven), **BROKEN** (verified bad — something
the CEO relies on will misbehave), or **OFF** (intentionally disabled). Each
non-WORKING check carries a remedy line and an `auto_fixable` flag.

Then repair, in escalation order:

1. **Auto-fix the safe class** — `ernest heal` applies only `auto_fixable` fixes
   (regenerate a corrupt grading rubric from code defaults, recreate a missing
   vault dir, restore broken concerns YAML from the last-good snapshot). Each fix
   is snapshotted, applied, then **re-verified** — and rolled back if it doesn't
   clear the check. Logged to `logs/repairs.jsonl`.
2. **Confirm nothing else regressed** — `ernest selftest` runs a sandboxed smoke
   check (watch + brief + grade on sample data + the gate self-test).
3. **Guided fixes for the rest** — for anything not auto-fixable:
   - Missing tool/MCP connector → research the right server on the web, propose
     the exact `claude mcp add` / `.mcp.json` change, apply on approval.
   - Missing skill → scaffold via `ernest-use-case-author`.
   - Needs credentials/login → stop and ask the CEO.

Rules:

- Apply only safe, reversible, in-workspace fixes directly (that's exactly the
  `ernest heal` class); propose anything that touches credentials, sends,
  installs, or external systems.
- Web research is expected for unknown breakage. Always verify by re-running
  `ernest doctor` (or `ernest selftest`).
- Recurring breakage → offer to make the fix permanent (skill / automation /
  note) so it can't recur silently.
