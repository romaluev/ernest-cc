# Local Data Fallback

This folder lets Ernest work without the VPS brain and without live app MCPs.

Use it for dry-runs, demos, or a locked-down local install:

- `data/mail/` — exported email threads, `.eml`, `.mbox`, `.md`, `.json`, or `.csv`.
- `data/hubspot/` — exported contacts, companies, deals, and activity CSV/JSON files.
- `data/calendar/` — exported calendar agenda files.

Ernest should prefer live local MCP connectors when they are configured. If no
connector exists, it may read these files and produce reminder cards/drafts from
the exported data. It must label outputs as `source: local-export`.
