# /ernest-learn

Use `ernest-use-case-author` on recent learning notes.

Goal: propose at most one governed improvement from the last week.

Inputs:

- `logs/learning-proposals.jsonl`
- recent watch cards
- CEO approvals, edits, rejections, and ignored suggestions

Rules:

- Proposal-only.
- At most one improvement per run.
- Never auto-adopt new skills, credentials, sends, or permission expansion.
- Include rollback and dry-run.
- If no high-confidence improvement exists, return `[SILENT]`.

Deterministic baseline: `ernest learn` aggregates `logs/learning-proposals.jsonl`
into `logs/learning-summary.md`, all marked `status: proposed` and requiring CEO
approval. `ernest learn --note "..."` adds an observation by hand.
