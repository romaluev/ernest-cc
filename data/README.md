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
- `data/linkedin/` — LinkedIn inbound export. `*.csv` with the columns below;
  `Connections.csv` is skipped (that is the network, not the queue). Written by
  `adapters/linkedin/ingest.py`, never by hand.
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
- `data/support/tickets.csv` — sample support queue (Pylon/Zendesk shape) for support-triage demos.
- `data/calls/fireflies-2026-06-24-apex.md` — sample call transcript for call-prep/call-coaching demos.
- `data/ashby/candidates.csv` — sample ATS pipeline for hiring-pipeline demos.

## LinkedIn invitation export format

`data/linkedin/invitations.csv`. Headers are matched case- and punctuation-
insensitively, so LinkedIn's own archive headers (`Sent At`, `From`,
`Inviter Profile URL`) and the live-DOM rung's snake_case both load:

```csv
name,public_url,urn,headline,company,location,note,sent_at,mutual_connections,connections,invitation_type,direction
```

- Only `direction=received` and `invitation_type=connect` rows are triaged.
  Company follows and newsletter subscriptions arrive on the same surface and
  would inflate every count on the report.
- `mutual_connections` and `connections` are **blank when unknown**, never `0`.
  Blank means "we did not look"; `0` means "we looked and found none". The
  grader scores those differently and the archive rung carries neither, so it
  leaves both blank. **Missing is not zero.**
- Dedup is by `public_url` slug, falling back to `urn`, falling back to a
  normalized name. The same human arrives once by slug and once by member URN
  (`ACoAA…`) — see `identity_key` in `ernest/grading.py`.
- `sent_at` should be ISO (`YYYY-MM-DD`). Relative stamps ("1 month ago") are
  the adapter's job to normalize before writing, not the engine's to guess.
