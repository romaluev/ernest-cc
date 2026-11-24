# /ernest-draft

Draft actions for a specific reminder card or explicit CEO request.

Arguments may include:

```yaml
card_id:
playbook:
account:
profile:
```

Process:

1. Identify the relevant card or playbook.
2. Load the playbook's Draft half.
3. Use the `ernest-draft` subagent if multiple drafts or heavy retrieval are needed.
4. Prepare a reviewable approval batch.

Rules:

- Never send.
- Never update CRM stages.
- Never create calendar invites.
- Include facts used, uncertainties, and approval checklist.

Deterministic baseline: `ernest draft --concern <id>` (or `--contact <name>`)
writes labeled draft-only outreach to `00-Drafts/`. It never sends; approving a
send is a separate human step through a connector.
