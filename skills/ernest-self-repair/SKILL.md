---
name: ernest-self-repair
description: Diagnose and fix Ernest itself when something is broken or missing — a tool/MCP connector isn't available, a command errors, a skill is missing, doctor reports issues, or a step silently fails. Use when the user says "fix it", "why isn't this working", "set this up", "a tool is missing", or when you hit a capability gap mid-task. Research best practices on the web, propose concrete fixes, apply safe ones, and escalate risky ones for approval.
version: 1.0.0
---

# Ernest Self-Repair

Ernest should not make the CEO debug it. When a capability is missing or broken,
**diagnose → research → fix → verify**, within the approval rules. Don't just
report a wall; find the way through it.

## 1. Diagnose

```bash
ernest doctor
```

Read the `diagnostics:` block (each item has a `fix:`). Also classify the actual
failure you hit:

- **Missing MCP connector / tool** (e.g. no Gmail, Slack, HubSpot, Sheets).
- **Broken/erroring command** (Python traceback, bad config, missing file).
- **Missing skill/automation** for what's being asked.
- **Missing or stale data** (empty `data/`, no live source).
- **Permission/auth** (connector needs login or a token).

## 2. Research (use the web — this is expected)

For a missing or unfamiliar tool, look it up before guessing:

- Search for the **official / well-maintained MCP server** for that app
  (prefer first-party or Anthropic-listed servers), its install command, and its
  read vs write tool names.
- Search current best practices / docs when a config or API is unclear.
- Prefer authoritative sources (official docs, vendor repos) over random blogs.

Capture what you learned in one or two lines of grounding before acting.

## 3. Fix

Match the fix to the failure, and to the approval level:

| Situation | Action | Approval |
|---|---|---|
| Missing in-workspace file/dir, scaffold, or rubric value | Create/restore it directly | L0/L1 |
| Missing skill/automation | Use `ernest-use-case-author` to scaffold it | L1 (review) |
| Missing MCP connector | Propose the exact `claude mcp add ...` / `.mcp.json` edit; apply only on approval | **L2** |
| Needs login / token / credential | Stop and ask the CEO to authorize | **L3 — manual** |
| External install / system change | Propose command + reason; run only on approval | **L2/L3** |

Safe, reversible, in-workspace fixes (create a missing folder, restore a rubric
key from defaults, scaffold a skill) you may apply directly, then say what you
did. Anything touching credentials, sends, installs, or external systems is
**propose-first** — never self-grant.

## 4. Verify

Re-run the thing that failed (and `ernest doctor`). Confirm the diagnostic
cleared. If not, iterate once with new evidence; if still blocked after a
reasonable attempt, report precisely what's blocking and the single best next
step (don't loop).

## 5. Make it stick

If the fix is something that'll recur, offer to capture it permanently:

- a new skill/automation (`ernest-use-case-author`),
- a note for the weekly improvement loop (`ernest learn --note "..."`),
- or an edit to a rubric/standing-concern.

## Hard rules

- Never self-grant credentials, external-send permission, or new memory scope.
- Web research is allowed and encouraged; applying external changes is not,
  until approved.
- Prefer the smallest reversible fix. Always state what you changed and how to
  roll back.
