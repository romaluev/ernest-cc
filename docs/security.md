# Security

## Draft-First

External sends, posts, calendar invites, CRM writes, and similar live mutations are blocked by `hooks/pre_tool_use.py` before execution.

Prompt rules are not enough. The deterministic hook is the guarantee.

## Approval Levels

- L0: read, search, classify, summarize, reminder cards.
- L1: reversible internal memory/config update.
- L2: external drafts and CRM proposals; CEO approval required.
- L3: legal, money, contracts, irreversible deletes, credentials, permission expansion.

## Secret Handling

- Do not commit `.env`, secrets, tokens, or private files.
- In VPS mode, app connector tokens stay on the VPS brain.
- Local mode is explicit and should use only reviewed local MCP servers.

## Filesystem Scope

Allowed writes:

- `memory/**`
- `logs/**`
- `${ERNEST_LOCAL_VAULT}/**`

Denied:

- `.env`
- files containing `secret`
- files containing `token`
- project `private` folders

## Self-Improvement Safety

The learning hook writes proposal candidates only. It does not modify skills or permissions.

Every improvement needs:

- dry-run
- approval level
- rollback
- north-star rationale
