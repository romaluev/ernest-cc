# /ernest-doctor

Use the `ernest-self-repair` skill. Diagnose Ernest and fix what's broken or
missing so the CEO doesn't have to.

Baseline:

```bash
ernest doctor
```

Then, for each diagnostic:

- Missing tool/MCP connector → research the right server on the web, propose the
  exact `claude mcp add` / `.mcp.json` change, apply on approval.
- Broken command / missing file → restore or scaffold the safe, in-workspace fix.
- Missing skill → scaffold via `ernest-use-case-author`.
- Needs credentials/login → stop and ask the CEO.

Rules:

- Apply only safe, reversible, in-workspace fixes directly; propose anything that
  touches credentials, sends, installs, or external systems.
- Web research is expected. Verify by re-running `ernest doctor`.
- Offer to make recurring fixes permanent (skill / automation / note).
