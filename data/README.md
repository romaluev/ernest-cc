# Local Data Fallback

This folder lets Ernest work without the VPS brain and without live app MCPs.
It powers dry-runs, demos, and a locked-down local install.

Ernest prefers live sources when configured (VPS brain, then local MCP
connectors). If none exists, it reads these exported files and produces
remind/assign cards. It labels outputs `source: local-export`.

## Layout

- `data/mail/` — exported email threads (`.md` with a small header, or `.json`).
  Header fields the engine reads: `contact`, `company`, `last_inbound`,
  `last_outbound`, `intent`, `category`, `participants`, `subject`, `status`.
- `data/hubspot/` — exported contacts CSV (`email,firstname,lastname,company,tier,last_touch,next_action`).
- `data/lists/` — curated lists to reconcile against (HubSpot list exports,
  Google Sheet exports). Any CSV; the concern names the key column.
- `data/sourcing/` — sourcing pipeline CSV (`name,linkedin,purpose,status,note`).
- `data/slack/` — exported tasks CSV (`task,owner,status,due,source`).
- `data/calendar/` — exported calendar agenda files (optional).

## How a Google Sheet becomes a list

Export the sheet to CSV (File -> Download -> CSV) and drop it in `data/lists/`,
or connect a Sheets MCP so Ernest reads it live. The `list-sync` concern then
reconciles it against the matching email category.
