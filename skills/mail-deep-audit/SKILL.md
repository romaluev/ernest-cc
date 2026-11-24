---
name: mail-deep-audit
description: Full-window owed-reply audit over live mail or exports. Chunked sweep — finish every bucket before summarizing. Remind only unless CEO asks to draft.
version: 1.0.0
---

# Mail Deep Audit

Use when the CEO asks for a **full back-catalog sweep** — e.g. "audit the last year",
"every thread I owe a reply on", or "don't stop at this week".

This is **not** the same as daily `/ernest-watch` (which uses short staleness defaults).

## Parameters

```yaml
window: "365d"       # total lookback
staleness: "7d"      # minimum days waiting before flagging
chunk_days: 30       # MCP search bucket size
exclude: "newsletters,job-seekers,cold-vendors"
```

## Non-Negotiable Rules

1. **Complete the full window** before the final summary.
2. **Do not stop** after the first page, first week, or "most recent cluster".
3. **Do not ask** "want me to keep going?" mid-audit unless a connector is blocked.
4. **Remind only** — no drafts until `draft these`.
5. Label importance from email content when HubSpot is unavailable; note the caveat once.

## Run Sequence

### 0. Baseline (optional)

```bash
ernest audit --window 365d
```

Reads `00-Watch/audit-manifest--<date>.md` for chunk list. On local exports,
also writes `mail-audit--<date>.md` if data exists.

### 1. Load manifest

Read the manifest from the latest `audit-manifest--*.md` in `00-Watch/`, or build
chunks yourself: split `window` into `chunk_days` buckets from today backward.

### 2. Chunked mail search (live MCP)

For **each chunk** (newest → oldest):

1. Search Inbox threads with last inbound in `[chunk.start, chunk.end]`.
2. Cross-check Sent — drop threads where you already replied after their last message.
3. Classify intent (revenue, investor, partnership, press, hire, noise).
4. Append to a running deduped list (key: thread id or from+subject).

Data sources (first available):

- VPS: `mcp__ernest-brain__search_mail`
- Local MCP: configured Gmail / Microsoft mail tools
- Exports: `data/mail/**` (label `source: local-export`)

### 3. Rank and filter

- Rank: tier (if HubSpot available) → revenue/investor/partnership → days waiting.
- Exclude noise per `exclude` unless CEO overrides.
- Split **actionable** vs **optional/low-signal** in the summary.

### 4. Write one consolidated card

Path: `00-Watch/mail-audit--<date>.md`

Include:

- `window`, `staleness`, `chunks_completed`, `source`
- Every actionable owed thread with days waiting and one-line context
- Noise excluded (categories)
- HubSpot availability caveat if tier was inferred from email only

End with:

`Reply draft these when you want me to prepare actions.`

## When Not To Use

- Daily ambient watch → `/ernest-watch` or `ernest start`
- Single account recovery → `account-followup-recovery` with `account: "<name>"`
- Drafting → only after explicit `draft these`
