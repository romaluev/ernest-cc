# Local Data Fallback

This folder lets Ernest work without the VPS brain and without live app MCPs.
It powers dry-runs, demos, and a locked-down local install.

Ernest prefers live sources when configured (VPS brain, then local MCP
connectors). If none exists, it reads these exported files and produces
remind/assign cards. It labels outputs `source: local-export`.

## Layout

- `data/mail/` — exported **email threads** with full message bodies.
- `data/slack/threads/` — exported **Slack threads** (same format as mail).
- `data/messages/` — optional other channels (Teams, Discord, etc.).
- `data/hubspot/` — exported contacts CSV.
- `data/lists/` — curated lists to reconcile against.
- `data/sourcing/` — sourcing pipeline CSV. Columns: `name,linkedin,purpose,
  status,note,company,title,profile`. For talent (`purpose=hire`), fill
  `profile` with the candidate's career summary — that's what the grader reads.
- `data/grading/` — editable ICP rubrics: `b2b-rubric.json`, `talent-rubric.json`
  (company/provider lists, AI-media models, Tier-1 countries, intent keywords).
  Extend these lists; grading uses CRM > these lists > inference.
- `data/slack/tasks.csv` — task tracker export (owners/due dates).
- `data/calendar/` — optional calendar exports.

## Full thread export format

Header fields the engine reads: `thread_id`, `channel` (`email` | `slack` | …),
`contact`, `company`, `last_inbound`, `last_outbound`, `intent`, `category`,
`participants`, `subject`, `status`.

After a `---` line, include **every message**:

```markdown
### 2026-06-18 | Alex Example (inbound)
Full message body — not a one-line summary.

### 2026-06-10 09:30 | Sam (outbound)
Your prior reply.
```

Or JSON with a `messages` array: `{ "at", "from", "direction", "body" }`.

`ernest read` caches parsed threads to `~/ErnestVault/Ernest/00-Threads/`.
`ernest start` auto-reads owed threads from exports before watch.

## How a Google Sheet becomes a list

Export the sheet to CSV (File -> Download -> CSV) and drop it in `data/lists/`,
or connect a Sheets MCP so Ernest reads it live. The `list-sync` concern then
reconciles it against the matching email category.
