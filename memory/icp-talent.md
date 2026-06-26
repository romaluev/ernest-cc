# ICP — Talent Grading

How Ernest grades talent for outreach. The **current** outreach plan targets the
**ex-NovaLabs** alumni pool — but this is a snapshot that will change. The pool
and the signal lists are living config, not hardcoded.

**To change the criteria** (no code edits): edit `data/grading/talent-rubric.json`
(`pool`, Big-Tech names, AI-media models, Tier-1 countries, etc.), or just tell
Ernest — e.g. "switch our talent focus from ex-NovaLabs to ex-FAANG designers";
it updates the rubric and re-runs `ernest grade --talent`. The tiers below apply
to whatever the current pool is.

## Signal priority

1. **CRM / ATS** if connected (stage, prior contact, owner).
2. **Curated lists** — `data/grading/talent-rubric.json` (Big Tech names, AI
   media models, Tier-1 countries, senior titles).
3. **Inference** from the candidate's profile/career summary. Flag judgment
   calls (especially "likely interested") for a human.

## Hard filter (applies to every tier)

A candidate is only a target if they are **likely to be interested in working
with / on Northwind** AND are **not currently a Northwind investor or
employee**. If they're a current investor/employee → not a sourcing target
(treat as Trash for sourcing purposes), regardless of pedigree.

## Tier 1 — pursue

Any one of these (and passes the hard filter):

- Strong B2B or B2C experience built in Tier-1 countries (US, UK, EU, etc.).
- Strong technical base (deep engineering/ML/research foundation).
- Worked in Big Tech in a high position (Team Lead and up counts).
- Strong in AI media products (generative video/image, creative AI).

Action: prioritize for warm, personalized outreach. Assign an owner.

## Tier 2 — worth a look

- Any Big Tech experience working on Product or GTM.
- Any experience at US startups.
- Has worked with AI media models (diffusion, video/image generation, etc.).

Action: keep in pipeline; lighter-touch outreach.

## Tier 3 — Trash

- None of the above. Don't spend outreach effort.

## Notes

- "Likely interested" is a judgment call — base it on trajectory (e.g. building
  in AI media, restless at a slow org, prior creator/consumer-AI work), and flag
  confidence. Never assert interest you can't ground.
- Prefer evidence from the actual profile over assumptions about a company name.
