# Run Ernest in Claude Cowork

Cowork is the desktop app (Mac/Windows) — same Ernest as Claude Code, but no
terminal. You install and drive it entirely by chat. It runs the same safety gate
and connects to your tools through Cowork's Connectors UI. Best for a non-technical
user who just wants to talk to it.

## Quick start

1. **Install the plugin.** Open the plugin browser (the **+** / `/` menu) → add the
   Ernest marketplace (`romaluev/ernest-cc`) → install **`ernest-cc`**.
2. **Set it up by talking.** Run **`/ernest-setup`** and answer ~5 plain questions
   (keep everything on this machine? your name & company? what's a good lead? anything
   I must never do? which tools to watch?).
3. **Connect tools (optional).** Open **Settings → Connectors** to add Gmail / Slack /
   HubSpot / Calendar. Until you do, Ernest runs on sample data — it never fakes real data.

No files, no commands to memorize.

## Try these (2–3 requests)

```text
What needs me today?
```

```text
Make sure my colleague is on every B2B intro thread where they're missing.
```

```text
Find B2B sales/marketing candidates in my inbox and draft follow-ups for review.
```

Reply **"draft these"** whenever you want replies prepared. Nothing is ever sent
without your approval.

## Safety

Cowork runs the same **deterministic gate** as Claude Code (the plugin's PreToolUse
hook fires here too): sends and live CRM writes are blocked in code and become drafts.

## On your phone / remote

Cowork is a desktop app — there's no phone client. Two ways to get mobile/remote use:

1. **Always-on desktop.** Keep a desktop running Cowork and remote into it from your
   phone. Good if you want the exact Cowork experience on the go.
2. **Use [Hermes](hermes.md) instead.** The Telegram bot is natively mobile and runs
   24/7 on the server — the simplest "Ernest on your phone." It needs Composio
   connected (in your approved apps) to reach live tools.

## Where next

- [daily-use.md](daily-use.md) — driving it day to day
- [examples.md](examples.md) — more prompts
- [plus-vps.md](plus-vps.md) — share one memory with the 24/7 server
