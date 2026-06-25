---
name: sourcing-pipeline
description: Track partnership/hire targets and surface who still needs outreach. Remind/assign only.
version: 1.0.0
---

# Sourcing Pipeline

CSV-backed pipeline: `name,linkedin,purpose,status,note`. Status `new` surfaces on watch; `contacted`/`done` do not.

## Parameters

```yaml
source: "data/sourcing/targets.csv"
purpose: "partnership/hire"
```

Deterministic: concern `partnership-sourcing`. Discovering new targets needs a search connector; tracking works offline.
