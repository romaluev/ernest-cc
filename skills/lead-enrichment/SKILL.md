---
name: lead-enrichment
description: Enrich a lead, contact, company, or sourcing target with firmographics and signals so grading and outreach are accurate. Use when the CEO asks "who is this", "enrich this lead/list", "fill in company info", or before grading/outreach when data is thin. Read + propose; CRM writes are draft-first.
version: 1.0.0
---

# Lead Enrichment

Thin records produce bad grades and generic outreach. This skill fills the gaps
using Clay + Apollo, then feeds `b2b-lead-grading` and `talent-sourcing-grading`.

## Inputs

```yaml
target: ""           # person, company, domain, or a list/CSV
fields: "role,seniority,company_size,industry,funding,location,signals"
purpose: "grade"     # grade | outreach | sourcing
```

## Data sources (read-only; swappable)

- **Clay** MCP — waterfall enrichment (company, person, signals).
- **Apollo** MCP — contact/firmographic data, titles, headcount.
- **Web** — recent public signals (raises, launches, hiring) when enrichment is thin.
- **HubSpot** — what we already know; avoid overwriting verified CRM facts.
- Export fallback: `data/enrichment/**`, `data/hubspot/**`.

## Run sequence

1. Resolve `target`; pull what HubSpot already has (CRM is canonical — don't clobber it).
2. Enrich missing `fields` via Clay, then Apollo; reconcile conflicts, keep provenance.
3. Add 1–3 timely signals relevant to Northwind's fit.
4. If `purpose=grade`, hand the enriched record to the grading skill and return the tier.
5. Propose CRM updates as a **draft** (field → new value → source); never write directly.

## Output

Chat (house format): **Bottom line** (who/what this is + grade if requested),
then key enriched fields with sources, then proposed CRM updates (for approval).
For a list, write the enriched table to the digest and link it.

## Rules

- Read + propose only. HubSpot writes are draft-first; verified CRM data wins over inference.
- Mark every field's source (Clay / Apollo / web / CRM); flag low-confidence values.
- Respect data limits: business firmographics only; no scraping of private/personal data.
