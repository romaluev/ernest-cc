---
name: ernest-self-repair
description: Diagnose and fix Ernest itself when something is broken or missing — a tool/MCP connector isn't available, a command errors, a skill is missing, doctor reports issues, or a step silently fails. Use when the user says "fix it", "why isn't this working", "set this up", "a tool is missing", or when you hit a capability gap mid-task. Research best practices on the web, propose concrete fixes, apply safe ones, and escalate risky ones for approval.
version: 2.1.0
---

# Ernest Self-Repair

Ernest should not make the CEO debug it. When a capability is missing or broken,
**diagnose → heal → research → fix → verify**, within the approval rules. Don't
just report a wall; find the way through it. The escalation ladder (tiered
self-healing, `docs/research/self-improving-systems.md`):
deterministic auto-fix → this guided session → CEO decision.

## 1. Diagnose (machine-readable)

```bash
ernest doctor --json
```

Every check returns `{state, evidence, remedy, auto_fixable}` with four states:

- **WORKING** — verified good; skip it.
- **UNVERIFIED** — configured but unproven (e.g. an MCP connector never used
  this week). Verify cheaply if the task depends on it; otherwise note it.
- **BROKEN** — verified bad. This is your work queue, ordered below.
- **OFF** — intentionally absent (local-exports mode, not onboarded). Only act
  if the CEO's actual request needs it turned on.

A crash of any `ernest` command is auto-captured to `logs/repairs.jsonl` and an
`ernest-health--<date>` card — check both for context you didn't see live.

## 2. Heal first (deterministic, zero-risk)

```bash
ernest heal
```

This applies ONLY the safe class — restore `standing-concerns.md` / grading
JSONs from last-good snapshots (`logs/snapshots/`), regenerate defaults, recreate
dirs — and every fix is verified by re-running the failed check, logged to
`logs/repairs.jsonl`, with the broken file preserved in `logs/repairs/`. Then it
runs the sandbox selftest. If heal clears everything, verify (step 5) and stop.

## 2b. Updating Ernest — never via web fetches (they're blocked by design)

If the ask is "update Ernest" / "install the latest version" / "check what's new":

- **Do NOT try to fetch github.com** (WebFetch or curl). In local mode the gate
  denies web egress, so the fetch comes back empty — that is the gate working,
  **not evidence the repo is private, moved, or unreachable**. Never tell the
  CEO the repo "may be private" based on an in-session fetch.
- The sanctioned path is the engine's own updater, which the gate allows:

```bash
ernest update            # fetch -> validate -> install -> verify, auto-rollback
ernest update status     # current commit, channel, pending/rollback state
ernest --version         # what's installed right now
```

- Ernest also updates itself daily at 07:30 (`ernest schedule`), so "you're
  already current" is checked with `ernest update` — it prints `already current`
  when there's nothing new. `ernest doctor` shows update-channel reachability.
- If `ernest` isn't on PATH here (plugin-only surface with no standalone
  install), say exactly that: updates for the plugin come from re-fetching the
  plugin in the plugin browser; the standalone install is what auto-updates.

## 3. Research what heal can't fix (use the web — this is expected)

For each remaining BROKEN/needed item, look it up before guessing:

- Missing connector → find the **official / well-maintained MCP server** for
  that app (prefer first-party or Anthropic-listed), its install command, and
  its read vs write tool names.
- Erroring command → the captured traceback is in `logs/repairs.jsonl`; search
  the exact error. Prefer official docs/vendor repos over random blogs.
- Capture what you learned in one or two lines of grounding before acting.

## 4. Fix by failure class

| Check / situation | Action | Approval |
|---|---|---|
| `concerns.parse`, `grading.*`, `memory.preferences` BROKEN | `ernest heal` (already attempted in step 2; if it reported `fix-unavailable`, the snapshot is missing — restore from repo/git or re-onboard) | L0/L1 |
| `grading.*` UNVERIFIED "lacks key(s)" | The JSON **replaces** code defaults wholesale — a missing key silently disables that signal family. Copy the missing key back from `ernest/grading.py` `_DEFAULTS`, keep the CEO's list edits, re-run `ernest grade` | L1 (say what you restored) |
| `memory.core` BROKEN (company-core / ceo-persona missing) | Never invent identity. Restore from git/repo if available, else run `/ernest-onboard` | L1 |
| `connectors.brain` BROKEN | Probe the URL; if the VPS is down propose `/ernest-go-local` as the interim; fixing the VPS is its own task | L1 (mode switch) |
| "Update Ernest" / GitHub "looks private/empty" from chat | §2b: the gate blocks web fetches by design — run `ernest update` (allowed), never diagnose privacy from a blocked fetch | L1 |
| Missing MCP connector | Propose the exact `claude mcp add ...` / `.mcp.json` edit; apply only on approval | **L2** |
| `gate.selftest` BROKEN | Stop everything else. Reinstall (`./install.sh --refresh`); do NOT proceed with any send-adjacent work until it passes — the draft-first guarantee is the product | **escalate now** |
| Needs login / token / credential | Stop and ask the CEO to authorize | **L3 — manual** |
| External install / system change | Propose command + reason; run only on approval | **L2/L3** |
| Missing skill/automation | Scaffold via `ernest-use-case-author` / `ernest new-automation` | L1 (review) |

Safe, reversible, in-workspace fixes you may apply directly, then say what you
did. Anything touching credentials, sends, installs, or external systems is
**propose-first** — never self-grant.

## 5. Verify (mandatory — a fix that isn't verified doesn't count)

```bash
ernest doctor        # the failed check must now read WORKING (exit 0)
ernest selftest      # the daily loop end-to-end in a sandbox (exit 0)
```

Re-run the exact thing that originally failed. If still broken, iterate once
with new evidence; if blocked after that, report precisely what's blocking, the
single best next step, and leave the health card in place (don't loop, don't
delete the card — it's the escalation surface).

## 6. Make it stick

If the breakage was recurring (same `check` id appears ≥3× in
`logs/repairs.jsonl`), don't just fix it again — feed the improvement loop:

- `ernest learn --note "recurring: <check id> — <root cause>"` so the weekly
  pass proposes a durable change (guard, default, or automation), or
- a new skill/automation (`ernest-use-case-author`), or
- a rubric/standing-concern edit (L1, with the diff stated).

## Hard rules

- Never self-grant credentials, external-send permission, or new memory scope.
- Never weaken the gate, hooks, `ernest.yaml`, or tests to make an error go
  away — those are the product's guarantees (`scope.protect` blocks you anyway).
- Web research is allowed and encouraged; applying external changes is not,
  until approved.
- Prefer the smallest reversible fix. Always state what you changed and how to
  roll back (heal's snapshots + `logs/repairs/` give you both for free).
