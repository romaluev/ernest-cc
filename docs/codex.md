# Run Ernest in Codex

Ernest runs on the **OpenAI Codex CLI** as a thin adapter over the same core (engine
+ memory + skills). Same brain, different body. Best for Codex users who want the
local watch-and-draft work; for live *sending*, use Claude Code or Hermes (see Safety).

## Quick start

```bash
bash adapters/codex/setup-codex.sh
cd ~/.ernest-cc && codex --profile ernest
```

Setup is idempotent — it only adds an `ernest` profile, prompts, MCP, and `AGENTS.md`;
it won't disturb your existing Codex config.

## Try these (2–3 requests)

```text
What needs me today?
```

```text
Read the thread with <person/company> and draft a reply in my voice.
```

```text
Grade the new inbound leads and talent against my ICP, best first.
```

Or use the slash commands: `/ernest-brief`, `/ernest-grade`, `/ernest-draft`,
`/ernest-doctor`, `/ernest-setup`.

## Safety — read this

Ernest's strongest protection — a deterministic gate that blocks unsafe actions in
code — is a **Claude Code/Cowork feature** (a PreToolUse hook). **Codex has no
equivalent hook.** On Codex, draft-first is enforced by three softer layers:

1. a strict `AGENTS.md` (draft-first, safe-tools-only),
2. Codex's own `sandbox_mode = workspace-write` + `approval_policy = on-request`, and
3. draft-first MCP servers only (the brain exposes no send tools).

So on Codex, **don't wire in raw send-capable connectors** — that bypasses the
protections. For live sending of email/Slack/CRM, use the **Claude Code** build
(deterministic gate) or **[Hermes](hermes.md)** (Telegram). Codex is for the local,
read-and-draft work. Adapter internals: [`../adapters/codex/README.md`](../adapters/codex/README.md).

## On your phone / remote

The Codex mobile app won't run Ernest. Two paths for mobile/remote use:

1. **Always-on desktop.** Keep a desktop running and remote into it from your phone.
2. **Use [Hermes](hermes.md) instead** — the Telegram bot is natively mobile and 24/7.

## Where next

- [hermes.md](hermes.md) — the mobile / 24/7 surface
- [examples.md](examples.md) — more prompts
- [daily-use.md](daily-use.md) — driving it day to day
