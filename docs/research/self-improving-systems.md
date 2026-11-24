# Design basis: Ernest's self-improving & self-healing loops

Ernest's three loops are built on established agent-architecture patterns, not
invented from scratch. This note is the design rationale — if you wonder *why* a
loop works the way it does, the pattern below is the reason. Everything here is
implemented in `ernest/` and covered by `tests/`.

## The three loops

| Loop | Contract |
|---|---|
| Self-healing | detect → diagnose → auto-fix (safe class only) → verify → escalate to a card |
| Self-improving | capture → distill → propose (with evidence + diff + reverse-diff) → human adopt → measure → backtrack |
| Smart substrate | skills carry real criteria/thresholds ("knobs") so the improve loop has something concrete to tune |

## Pattern → where Ernest uses it

| Pattern | Ernest implementation |
|---|---|
| **Reflection** — an agent critiques its own output and stores the correction in memory instead of retraining ([Reflexion](https://arxiv.org/abs/2303.11366)) | `ernest/learn.py::capture` classifies corrections from a session ("wrong tier", "too long", "actually…") into typed candidates queued for review |
| **Growing skill library** — reusable, verified capabilities accumulate rather than resetting each run ([Voyager](https://voyager.minedojo.org/)) | Skills are versioned; proven-by-use skills persist, silent ones (a concern that fired nothing for 30 days) are proposed for retirement |
| **Accreting playbooks** — context is treated as a durable playbook that strategies are appended to, not overwritten (ACE / agentic context engineering) | `memory/` and the grading rubrics accrete; `ernest learn --adopt` appends, never wipes |
| **Recurrence gate** — a pattern must recur (≥3×) before it is promoted to a rule | `ernest learn` proposals are ranked by evidence count; no evidence, no proposal |
| **Versioned change + rollback** — snapshot before any self-change, gate the keep on a passing check, one-command restore | `ernest/improve.py`: snapshot → apply → sandbox `selftest` → keep or auto-revert; `logs/versions/`, `ernest learn --rollback <id>` |
| **Quality backtracking** — measure after every change; if outcomes get worse, propose the revert | Post-adopt telemetry is compared to pre-adopt; a regression auto-proposes its own rollback in the next report |
| **Four-state health audit** — every check reports a distinct state with a remedy line and a machine-readable form | `ernest/health.py`: WORKING / UNVERIFIED / BROKEN / OFF per subsystem; `ernest doctor` renders it, `ernest doctor --json` feeds the repair skill |
| **Tiered self-healing escalation** — auto-fix the safe class, surface the rest where the human already looks, page a person last | `ernest heal` fixes only the auto-fixable class (with verify-or-restore); everything else becomes a health card in the daily watch; unresolved → an `/ernest-doctor` session |
| **Verify-after-fix** — a fix that can't be verified is rolled back, not kept | `ernest heal` re-runs the failed check after each fix; `selftest` gates every promotion |

## Boundaries the loops must never cross (Ernest's constitution)

- `sync.yaml`: `max_auto_changes_per_run: 0`; forbidden auto-changes (credentials,
  send permissions, memory scope, legal/money, unvetted connectors); every
  proposal must carry a rollback path.
- `ernest.yaml` `scope.protect`: the gate, hooks, tests, settings, and the
  updater are write-denied to the runtime — the loop cannot disarm its own safety.
- Approval levels: `heal` may only touch the auto-fixable class inside
  `scope.write`; `learn --adopt` is an explicit CEO action (L2); only preference
  appends are L1-with-notification.

## Where this lives in the code

- Self-healing: `ernest/health.py`, `ernest/selftest.py`, `ernest heal` / `ernest doctor` / `ernest selftest` in `ernest/cli.py`, skill `skills/ernest-self-repair/`.
- Self-improving: `ernest/telemetry.py`, `ernest/learn.py`, `ernest/improve.py`, `ernest learn` in `ernest/cli.py`.
- Smart substrate: the grading model in `ernest/grading.py`, documented in `skills/b2b-lead-grading/` and `skills/talent-sourcing-grading/`.
- Tests: `tests/test_health.py`, `tests/test_learn_v2.py`, `tests/test_skill_contract.py`, plus the existing suite.
