# /ernest-onboard

Run Ernest's first-use onboarding.

Fast path: run `ernest doctor` to confirm health, then `ernest onboard` to seed
memory non-interactively. The steps below cover the guided, connector-aware flow.

1. Explain in one paragraph: Ernest extends the CEO on inbox, follow-ups, CRM, calendar, and ops work; everything external is draft-first.
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
6. Confirm defaults already enabled:
   - morning brief
   - dropped follow-up watch
   - inbound prospect watch
7. Run a dry-run `/ernest-brief`.

Do not ask the CEO to edit config files.
