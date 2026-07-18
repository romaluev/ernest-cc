# Research: how Ernest's self-improving & self-healing loops map to working systems

Every mechanism in Ernest's three loops is modeled on a system that runs in
production or ships as working code — nothing here is invented. This file is the
provenance map: if you wonder *why* a loop works the way it does, the donor
system is the answer. (Compiled 2026-07-19 from a research pass over the Claude
Code skill ecosystem, the Hermes Agent community, and the agent-architecture
literature.)

## The three loops

| Loop | One-line contract |
|---|---|
| Self-healing | detect → diagnose → auto-fix (safe class only) → verify → escalate to a card |
| Self-improving | capture → distill → propose (evidence + diff + reverse-diff) → human adopt → measure → backtrack |
| Smart substrate | skills carry real criteria/thresholds ("knobs") so the improve loop has something to tune |

## Mechanism → working example

| Ernest mechanism | Modeled on | What we took |
|---|---|---|
| Correction capture from sessions (`ernest/learn.py::capture`, Stop hook): "no, use X", "actually…", "too long", "wrong tier" → typed candidates queued for review | [claude-reflect](https://www.blog.brightcoding.dev/2026/03/24/claude-reflect-transform-claude-code-into-a-self-learning-powerhouse) (Claude Code hook plugin) | Correction-pattern classes; capture-at-the-moment-of-instruction; human-in-the-loop apply; <50ms hook budget |
| Closed skill loop with use-count telemetry and staleness (`logs/usage.jsonl`; `disable_stale` proposals: concern silent 30d → propose disable) | [UniM0cha/claude-self-improving-skills](https://github.com/UniM0cha/claude-self-improving-skills) + the Hermes curator (mined: `hermes-self-improving-research/08-hermes-self-improvement-loop-exact.md`) | stale-30d / archive-90d lifecycle; proven-by-use ages slower; usage counters as the aging signal |
| Promotion threshold: pattern seen ≥3× → propose rule/skill/concern | [self-improving-agent](https://github.com/alirezarezvani/claude-skills/blob/main/engineering-team/self-improving-agent/README.md) `/si:memory-review`; Hermes background review | The 2–3× recurrence bar before anything is promoted |
| Versioned apply + rollback for every self-change (`logs/versions/{file}@{ts}`, `ernest learn --rollback`) | [Hermes-Agent-1337-Inc](https://github.com/Gordey007/Hermes-Agent-1337-Inc) `skill_evolve.py` (`versions/SKILL.v<n>.md`, DoD-gated keep/rollback) + Ernest's own `sync.yaml` rollback-required rule | Snapshot-before-apply; gate the keep on a passing check; one-command restore |
| Quality backtracking: post-change telemetry worse than pre-change → auto-propose revert | Sam Desigan's grant scout (mined UC-H02: skill "updates or backtracks" per-run by comparing output quality) | Measure after every adopt; the system proposes its own rollback |
| Four-state health audit with per-check remedy + `auto_fixable` flag (`ernest/health.py`) | [last30days](https://github.com/mvanhorn/last30days-skill) `doctor` (WORKING / TURNED ON – UNVERIFIED / NOT WORKING / COULD BE ON) | The 4-state taxonomy; remedy line per check; machine-readable output |
| Escalation chain: auto-fix → health card in the daily flow → human session | 4-tier production self-healing ([70-production-bugs writeup](https://dev.to/_d7eb1c1703182e3ce1782/how-to-build-a-self-healing-ai-agent-system-lessons-from-70-production-bugs-2nep), [recovery patterns](https://zylos.ai/research/2026-03-02-ai-agent-self-healing-recovery-patterns/)): supervisor → health check → AI diagnosis → human page | Never auto-fix past the safe class; every escalation lands where the human already looks (the watch card) |
| Verify-after-fix or restore; selftest gates any promotion (`ernest heal`, `ernest selftest`) | Ernest's own `gate.selftest()` + `scripts/self-update.sh` promotion gate — extended, not invented | A fix that can't be verified is rolled back, not kept |
| Skill library + iterative refinement with environment feedback and self-verification | [Voyager](https://voyager.minedojo.org/) (ever-growing executable skill library); [Reflexion](https://stackviv.ai/blog/reflection-ai-agents-self-improvement) (verbal self-critique in episodic memory); ACE (contexts as accreting playbooks) | The theory frame: skills accumulate, critiques persist, playbooks accrete instead of resetting |
| Evidence-ranked proposals ("3 corrections mention X") instead of vibes | CLCK agency pattern (mined UC-B02: "each human edit is signal for the next skill revision"); Hermes `.usage.json` | Proposals cite their evidence count; no evidence, no proposal |

## Boundaries the loops must never cross (Ernest's constitution)

- `sync.yaml`: `max_auto_changes_per_run: 0`; forbidden auto-changes (credentials,
  send permissions, memory scope, legal/money, unvetted connectors); rollback
  path required on every proposal.
- `ernest.yaml` `scope.protect`: the gate, hooks, tests, settings, and the
  updater are write-denied to the runtime — the loop cannot disarm its own
  safety (the same property the 1337-Inc design gets from its immutable
  DoD evaluator).
- Approval levels: `heal` may only touch the auto-fixable class inside
  `scope.write`; `learn --adopt` is an explicit CEO action (L2); only preference
  appends are L1-with-notification.

## What to read next

- `hermes-self-improving-research/00-hermes-core-mechanics.md` and
  `08-hermes-self-improvement-loop-exact.md` (local research corpus) — the
  fullest documented production self-improvement loop.
- `~/Documents/Last30Days/hermes-use-case-library/` — 119 deepened use cases
  with the mined instruments this repo's skills adapt.
