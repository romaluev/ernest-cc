# Run Ernest in Claude Code

Claude Code is the terminal/IDE build. It's the most capable surface: the full
deterministic safety gate runs here, and you get live mail/CRM/Slack search through
native MCP connectors. Best for a power user at a keyboard.

## Quick start

**In the app (no terminal):** open the plugin browser (the **+** button) → add the
Ernest marketplace (`romaluev/ernest-cc`) → install **`ernest-cc`** → run
**`/ernest-setup`** and answer ~5 plain questions.

**Terminal:**

```bash
./install.sh        # once — checks prereqs, installs to ~/.ernest-cc, prints your first brief
ernest start        # daily: what needs you (nothing is sent)
ernest schedule     # optional: prepare the morning brief automatically
```

Either way, setup is conversational and local-first — no files to edit, nothing
leaves your machine by default.

## Try these (2–3 requests)

```text
What needs me today?
```
Returns a ranked brief of open loops — dropped follow-ups, quiet deals, threads you owe.

```text
Who did I drop the ball with this quarter? Search everywhere and skip anything already handled.
```
Searches mail + HubSpot + Slack + calendar and cross-checks each item for resolution
before flagging it.

```text
Draft replies for the top 3, in my voice.
```
Prepares drafts grounded in the full thread — shown for review. You send them yourself.

## Safety

Claude Code enforces the **deterministic gate** (a PreToolUse hook): sends, posts,
and live CRM writes are blocked in code and turned into drafts, regardless of what
the model is asked to do. This is the strongest enforcement of any surface.

## On your phone / remote

Claude Code is a desktop/CLI tool — it doesn't run on a phone. For genuinely mobile,
24/7 access use **[Hermes](hermes.md)** (the Telegram bot). If you specifically want
Claude Code remotely, run it on an always-on desktop and remote into that machine.

## Where next

- [daily-use.md](daily-use.md) — driving it day to day
- [examples.md](examples.md) — more prompts, simple → complex
- [connectors.md](connectors.md) — connect Gmail / Slack / HubSpot (native MCP)
- [plus-vps.md](plus-vps.md) — share one memory with the 24/7 server (`/ernest-connect-brain`)
