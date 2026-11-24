# Ernest on Codex (adapter)

Ernest is one **core** (engine + memory + skills + the brain contract) behind thin
**adapters**: Claude Code/Cowork (the plugin), Hermes/VPS (Telegram/Slack), and this
one — **OpenAI Codex CLI**. Same brain, another body.

## Install (one command)

```bash
bash adapters/codex/setup-codex.sh
```

It's idempotent and additive — it adds an `ernest` Codex profile, MCP servers,
`/ernest-…` prompts, and `AGENTS.md`, without rewriting your existing Codex config.
Honors `$CODEX_HOME`. To connect the optional remote brain, set `ERNEST_BRAIN_URL`
(+ `ERNEST_BRAIN_TOKEN`) before running.

## Use

```bash
cd ~/.ernest-cc        # so AGENTS.md + the engine are picked up
codex --profile ernest
```

Then talk to it, or use a slash command: `/ernest-brief`, `/ernest-grade`,
`/ernest-draft`, `/ernest-doctor`, `/ernest-setup`, `/ernest-watch`.

## Safety on Codex (read this)

Codex has **no PreToolUse hook**, so Ernest's deterministic gate (its Claude Code
guarantee) does **not** run here. Instead, draft-first is held three ways:

1. **`AGENTS.md`** states draft-first + safe-tools-only as hard rules.
2. **Codex's own guardrails** — the `ernest` profile runs `sandbox_mode = workspace-write`
   (writes only the vault/memory in the working dir, no network, no outside writes) and
   `approval_policy = on-request` (asks before anything risky).
3. **Draft-first MCP only** — the Ernest brain has no send tools by contract.

Therefore: **do not add raw send-capable connectors** (a Gmail/Slack "send" MCP) to
this profile — that would bypass every protection. For live *sends*, use the Claude
Code build (which has the deterministic gate) or the Telegram bot. On Codex, keep to
the engine, local memory, and draft-first MCP.

## What works today vs. later

- **Today:** the engine (`start`/`watch`/`brief`/`grade`/`read`/`draft`/`doctor`) on
  your local/exported data, full memory, draft-first by the rules above. Local-first,
  nothing leaves the machine.
- **Live connectors on Codex:** route them through a running brain MCP server
  (`brain/server.py`, draft-first by contract). Until the brain is deployed as an HTTP
  endpoint, do live email/CRM on the Claude build or via Telegram.
