---
name: list-sync
description: Reconcile email contacts against an external list (HubSpot export or spreadsheet). Flag gaps. Remind/assign only.
version: 1.0.0
---

# List Sync

Keeps a curated list aligned with who appears in email.

## Parameters

```yaml
category: "korea"                          # email threads to consider
match_key: "company"
target: "data/lists/korea-hubspot.csv"     # list to reconcile against
target_key: "company"
list_name: "Regional HubSpot list"
```

## Watch half

1. Collect contacts in email for `category`.
2. Load target list (HubSpot MCP, Sheets MCP, or CSV export).
3. Flag email contacts missing from the list.

Deterministic: concerns like `korea-list-sync`, `press-list-sync`. Writes to CRM/sheet stay approval-gated.
