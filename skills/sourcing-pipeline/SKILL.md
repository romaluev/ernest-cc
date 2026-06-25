---
name: sourcing-pipeline
description: Manage a pipeline of partnership/hire targets to source and reach out to (e.g. ex-Skolkovo operators in the USA). Tracks status; surfaces who still needs outreach. Remind/assign only.
version: 1.0.0
---

# Sourcing Pipeline

Turn ad-hoc "find more people like X" into a tracked pipeline. The CEO drops
targets in; Ernest surfaces who still needs outreach.

## Parameters

```yaml
source: "data/sourcing/targets.csv"   # the pipeline file
purpose: "partnership/hire"
```

The pipeline file is a CSV: `name,linkedin,purpose,status,note`. `status` is one
of `new | contacted | done | skip`.

## Watch Half

1. Read the sourcing pipeline.
2. Surface every target whose status is not `contacted`/`done`/`skip`.
3. Write one card: "N sourced targets need outreach", with LinkedIn + notes.

No drafts. The action is "review and assign outreach".

## Sourcing new targets (needs a connector)

Finding new people (e.g. ex-Skolkovo operators in the USA, similar to a given
LinkedIn profile) requires a web/LinkedIn search connector. When one is
authorized, Ernest can propose new rows for the pipeline for CEO review. It
never adds or contacts people automatically.

## Deterministic baseline

`ernest watch` runs this for the `partnership-sourcing` concern and lists the
uncontacted targets from the pipeline file, with no model and no connectors.

## When Not To Use

Not for outbound sending. This manages the list and the assignment only.
