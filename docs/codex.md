# Using Ernest on Codex

Yes — Ernest runs on **OpenAI Codex CLI** too, as a thin adapter over the same core
(engine + memory + skills). One brain, three bodies: Claude Code/Cowork, Hermes/VPS
(Telegram), and Codex.

## Set it up (one command)

```bash
bash adapters/codex/setup-codex.sh
cd ~/.ernest-cc && codex --profile ernest
```

Then talk to it, or use `/ernest-brief`, `/ernest-grade`, `/ernest-draft`,
`/ernest-doctor`, `/ernest-setup`. The setup is idempotent and only adds an `ernest`
profile + prompts + MCP + `AGENTS.md` — it won't disturb your existing Codex config.

## What you get

The local engine (watch, brief, grade/rank, read threads, prepare drafts), your full
memory, and draft-first behavior — all local-first.

## Important: safety differs from the Claude build

Ernest's strongest safety — a deterministic gate that blocks unsafe actions in code —
is a **Claude Code/Cowork feature** (a PreToolUse hook). **Codex has no equivalent
hook**, so on Codex draft-first is enforced by:

1. a strict `AGENTS.md` (draft-first, safe-tools-only),
2. Codex's own `sandbox_mode = workspace-write` + `approval_policy = on-request`, and
3. draft-first MCP servers only (the brain has no send tools).

So on Codex, **don't wire in raw send-capable connectors** — that would bypass the
protections. For live *sending* of email/Slack/CRM, use the **Claude Code build**
(deterministic gate) or the **Telegram bot**. Codex is great for the local,
read-and-draft work.

Details + the adapter internals: [`adapters/codex/README.md`](../adapters/codex/README.md).

## Remote / phone

Codex mobile won't run Ernest. For remote access, use the **Telegram bot** (the VPS
build) — that's "Ernest on your phone" today. See [vps-brain.md](vps-brain.md).
