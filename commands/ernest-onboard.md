# /ernest-onboard

Optional personalization and connector setup. **Not required** — `./install.sh`
and `ernest start` work without this.

When onboarding:

1. Explain: Ernest handles follow-ups, assignments, and list sync over email.
   Daily use is `ernest start`. Prompts: `docs/examples.md`. Connectors are
   native MCP — not Composio (`docs/connectors.md`).
2. Check mode (VPS brain health if configured; else local exports + optional MCP).
3. Ask minimum: name, role, company, main pain point, mail provider, CRM.
4. Optional: sent-mail samples for voice grounding.
5. Update `memory/company-core.md`, `memory/ceo-persona.md`, `memory/north-star.md`.
6. Confirm enabled concerns in `memory/standing-concerns.md`.
7. Run `ernest start` or `/ernest-brief`.

Do not ask the CEO to edit config files.
