# Run Ernest in Hermes (Telegram, 24/7)

Hermes is the always-on build: Ernest runs on a small server and you talk to it over
**Telegram**. This is the only surface that is genuinely **mobile** and keeps watching
**overnight** while your laptop is off. Same draft-first behavior — it reminds and
drafts, never sends on its own.

## Quick start

**For the person using it (no setup):** open Telegram, DM the Ernest bot, and say
**"Hi Ernest."** Onboarding starts in the chat — it asks a few plain questions, then
gives you Composio links to connect your tools.

```text
Hi Ernest
```

**For whoever sets up the server (one time):** from the Hermes distribution
(the `ernest` repo), with a secrets file containing the VPS and API keys:

```bash
bash scripts/deploy-ernest.sh --secrets ~/ernest.secrets.env
```

This stands up the Telegram gateway, memory vault, watch crons, and firewall on the
VPS. The user only ever touches Telegram.

## Try these (2–3 requests)

```text
What needs me today?
```

```text
Follow up on the deals that went quiet — who, and what should I say?
```

```text
Track open tasks from Slack by owner so nothing slips.
```

Reply **"draft these"** to get replies prepared. Approve to send.

## Connect live tools — Composio

On Hermes, live tools (Gmail/Outlook, HubSpot, Slack, Calendar) are reached through
**Composio**. To use them, Composio must be in your **approved apps**, then you click
its Connect links once during onboarding. Until tools are connected, Ernest runs on
its memory and sample data — it never fabricates real results.

This is the fastest path to "Ernest on my phone": add Composio to approved apps and
connect from Telegram — no desktop required.

## Safety

The server enforces draft-first independently of the laptop: a VPS-side gate plus a
brain contract that exposes **no send/post/publish tool at all**. Connector tokens
live only on the server; nothing sensitive sits on your phone.

## Share state with your laptop (optional)

Point a laptop surface (Claude Code / Cowork) at the same server brain so they share
one memory, reminder set, and draft store — run **`/ernest-connect-brain`**. Details:
[plus-vps.md](plus-vps.md) and [vps-brain.md](vps-brain.md).

## Where next

- [plus-vps.md](plus-vps.md) — laptop + server sharing one brain
- [vps-brain.md](vps-brain.md) — the brain contract and server internals
- [examples.md](examples.md) — more prompts
