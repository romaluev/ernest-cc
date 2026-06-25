# /ernest-onboard

Run Ernest's first-use onboarding.

**CEO daily use is `./install.sh` then `ernest start` — onboarding is optional
and only needed to personalize memory or connect live mail/CRM.**

When onboarding:

1. Explain in one paragraph: Ernest extends the CEO on inbox, follow-ups, CRM, calendar, and ops work; everything external is draft-first. Day to day is `ernest start`; prompts are in `docs/examples.md`.
2. Check mode:
   - VPS brain: call `mcp__ernest-brain__health` if available.
   - Local fallback: confirm local memory path exists or ask installer to rerun.
3. Ask only the minimum:
   - CEO name, role, company.
   - Main thing they want off their plate.
   - Primary email/calendar provider.
   - HubSpot workspace/company.
4. Ask for 15-20 sent-email samples or permission to retrieve sent-mail examples through the connected mail tool.
5. Update `memory/company-core.md`, `memory/ceo-persona.md`, and `memory/north-star.md` as L1 internal writes.
6. Confirm defaults already enabled (see `memory/standing-concerns.md`): Manoj on B2B, candidates, VIP follow-ups, Korea/press sync, sourcing, Slack tasks.
7. Run `ernest start` or `/ernest-brief` to show the first brief.

Do not ask the CEO to edit config files.
