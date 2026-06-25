# Add Or Improve Automations

Use:

```text
/ernest-new-automation
```

## What The CEO Says

Examples:

- "Every Friday, check investor follow-ups and tell me who I owe."
- "When a potential B2B partner emails, make sure we follow up within 3 days."
- "Watch HubSpot deals where no one touched them for a week."

## What Ernest Does

1. Checks `ernest-library-index`.
2. Reuses an existing skill if possible.
3. If new behavior is needed, asks only the questions that matter.
4. Produces a proposal with:
   - trigger
   - data sources
   - output
   - safety level
   - dry-run
   - rollback

## Governance

Ernest may propose:

- new standing concerns
- new schedules
- new `SKILL.md` files
- skill patches
- memory/config updates

Ernest may not auto-approve:

- external sends
- new credentials
- new connectors
- legal/money authority
- wider memory access

## Replication Pattern

Every scalable automation should be a skill with:

- parameters
- watch half
- draft half
- output schema
- when not to use
- safety rules
