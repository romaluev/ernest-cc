# /ernest-audit

Use the `mail-deep-audit` skill.

Deep owed-reply sweep over a long window (default 365 days). **Finish every date
chunk before summarizing** — do not stop after the first recent batch.

Deterministic baseline:

```bash
ernest audit --window 365d
```

Then read `00-Watch/audit-manifest--<date>.md` and execute all chunks against live mail.

Rules:

- Remind only unless the CEO says `draft these`.
- Never send or mutate live systems without approval.
- Do not ask to continue mid-audit unless a connector is blocked.
