---
name: read-thread
description: Read full conversation threads from email, Slack, Teams, or other messaging before watch, audit, or draft. Fetch all messages — not just search snippets.
version: 1.0.0
---

# Read Thread

Ernest must **read full threads** before classifying importance, deciding if a
reply is owed, or drafting. Metadata and search snippets are not enough.

## When To Use

- Before `/ernest-watch`, `/ernest-audit`, or `/ernest-draft`
- When the CEO asks "read this thread" or "what did they actually say?"
- After `ernest read` caches exports — supplement with live MCP for missing bodies

## Non-Negotiable Rules

1. **Read every message** in the thread (or full Slack thread / DM history).
2. **Verify owed status** against Sent (email) or your last message (Slack).
3. **Label channel**: `email`, `slack`, `teams`, etc.
4. **Cache** to vault `00-Threads/<thread_id>.md` when you fetch live content.
5. Read-only — never send or post.

## Data Source Order

1. Vault cache: `00-Threads/<thread_id>.md` (from `ernest read`)
2. Local exports: `data/mail/`, `data/slack/threads/`, `data/messages/`
3. VPS brain MCP:
   - `mcp__ernest-brain__read_mail_thread`
   - `mcp__ernest-brain__read_slack_thread`
4. Local MCP (read tools only):
   - `mcp__gmail__get_thread` / `mcp__gmail__read_thread`
   - `mcp__outlook__get_message` / thread equivalents
   - `mcp__slack__get_thread` / `mcp__slack__read_channel_history`
   - Teams, Discord, Telegram — same pattern: **get thread / list messages**

Search tools (`search_threads`, `search_mail`) find candidates. **Always follow
with a read call** to load the full body.

## Export Format (offline)

Markdown under `data/mail/` or `data/slack/threads/`:

```markdown
thread_id: my-thread
channel: email
contact: Alex Example
...

---

### 2026-06-18 | Alex Example (inbound)
Full message body here.

### 2026-06-10 | Sam (outbound)
Prior message.
```

JSON: `messages: [{ "at", "from", "direction", "body" }]`

## Run Sequence

1. Resolve `thread_id` from watch card, CEO mention, or search result.
2. Check vault cache — use if fresh enough for the task.
3. Else load export or call MCP **read** tool for full messages.
4. Write/update `00-Threads/<thread_id>.md`.
5. Summarize with quotes grounded in actual message text.

## Engine Baseline

```bash
ernest read --owed              # cache all owed threads from exports
ernest read --thread <id>       # one thread
ernest start                    # auto-reads owed exports before watch
```

## Output Schema

```yaml
thread_read:
  thread_id: "<id>"
  channel: email|slack|teams|other
  message_count: <n>
  owed: true|false
  last_inbound_excerpt: "<quote from last their message>"
  cached_at: "<path in 00-Threads/>"
  source: local-export|mcp-live
```
