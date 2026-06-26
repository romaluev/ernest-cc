# /ernest-read

Use the `read-thread` skill.

Load **full conversation bodies** for email, Slack, or other messaging — not
search snippets alone.

Deterministic baseline:

```bash
ernest read --owed
ernest read --thread <thread_id>
```

Rules:

- Read every message in the thread before watch/audit/draft decisions.
- Cache to `00-Threads/` in the vault.
- Live MCP: use get/read thread tools after search — never classify from snippets only.
- Read-only — never send or post.
