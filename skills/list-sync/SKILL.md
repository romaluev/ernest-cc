---
name: list-sync
description: Reconcile the people in the CEO's email against an external list (a HubSpot list or a Google Sheet) and flag who is in email but missing from the list. Remind/assign only.
version: 1.0.0
---

# List Sync

Keep a curated list in step with reality. Used for "sync my Korea email with
Alvin's HubSpot list" and "sync the press list with the tracker sheet".

## Parameters

```yaml
category: "korea"                     # which email threads to consider
match_key: "company"                  # field on the email side to match on
target: "data/lists/korea-hubspot.csv" # the list to reconcile against
target_key: "company"                 # column in the target to match on
list_name: "Alvin's HubSpot Korea list"
```

## Watch Half

1. Collect the people/companies in email for `category`
   (VPS brain / HubSpot MCP / Google Sheets MCP -> `data/lists/**` and `data/mail/**`).
2. Load the target list (HubSpot list via MCP, or an exported CSV).
3. Flag every email contact whose `match_key` is not present in the target's `target_key`.
4. Write one card: "N email contacts missing from <list_name>."

No drafts. The action is "add to the list / sync".

## Sources

- HubSpot list: read via `mcp__ernest-brain__search_hubspot` or a HubSpot MCP.
- Google Sheet (e.g. the press tracker): read via a Sheets MCP, or export the
  sheet to CSV into `data/lists/` and the engine reconciles it offline.

## Deterministic baseline

`ernest watch` runs this for the `korea-list-sync` and `press-list-sync`
concerns against the exported CSVs, with no model and no connectors.

## When Not To Use

Not for bulk CRM imports or deduping. This only surfaces missing entries for
review; writing to HubSpot/Sheets stays approval-gated.
