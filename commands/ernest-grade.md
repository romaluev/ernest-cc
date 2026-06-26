# /ernest-grade

Grade and sort inbound B2B leads and sourced talent against Higgsfield's ICP.

- B2B leads → `b2b-lead-grading` skill (Tier-1 / Tier-2 / Trash)
- Talent (ex-Skolkovo pool) → `talent-sourcing-grading` skill (Tier-1 / 2 / 3)

Deterministic baseline:

```bash
ernest grade            # both
ernest grade --b2b      # leads only
ernest grade --talent   # talent only
```

Cards land in `00-Watch/`, sorted Tier-1 first, with reasons and `check:` flags.

Rules:

- Read full threads/profiles before grading — not snippets.
- Signal priority: CRM > curated lists (`data/grading/`) > inference.
- Resolve `check:` flags; flag low-confidence Tier-1 claims for Alex.
- Remind/assign only — never auto-reply or contact a candidate.
