# Quickstart

Two ways in. Most people want the first one.

## Option A — In Claude (no terminal) · recommended

Best for Cowork or the Claude desktop/Code app. Nothing to download by hand.

1. **Add Ernest.** In Claude, open the plugin browser (the **+** button)
   → add the Ernest marketplace → **install `ernest-cc`**.
   *(One-time: if asked for the marketplace, it's `romaluev/ernest-cc`.)*
2. **Set it up by talking.** Run **`/ernest-setup`**. Ernest asks ~5 plain questions
   (keep everything on this Mac? your name & company? who's a good lead? anything I
   must never do? which tools to watch?) and configures itself from your answers.
3. **Done.** Ask **"what needs me today?"** Reply **"draft these"** when you want
   replies prepared. Nothing is ever sent without your OK.

That's the whole setup. No files, no flags. By default **everything stays on your
machine** ([privacy.md](privacy.md)).

## Option B — Terminal (for power users / setting up for someone else)

```bash
./install.sh
```

The installer checks prerequisites, installs to `~/.ernest-cc`, puts an `ernest`
command on your PATH, and runs your first brief immediately. Then, daily:

```bash
ernest start          # what needs you today (remind-only; nothing sent)
ernest schedule       # run the morning brief automatically each day
```

No config files to edit.

## First thing you'll see

Ernest ships with sample data so the first run is real, not empty — slipping
follow-ups, VIPs who went quiet, inbound leads to triage, list/CRM gaps. Replace the
samples by connecting your tools (see [connectors.md](connectors.md)) or it keeps
using samples until you do — it never fakes real data.

## Updates

You don't update by hand. Ernest checks for updates, validates them, and shows a
one-tap **"apply update"** card; it auto-rolls-back on any problem and never touches
your memory. See [updates.md](updates.md).

## Running somewhere other than Claude?

Same Ernest, per-surface quick starts: [claude-code.md](claude-code.md) ·
[cowork.md](cowork.md) · [codex.md](codex.md) · [hermes.md](hermes.md) (Telegram, mobile/24-7).

## Where next

- [how-it-works.md](how-it-works.md) — the two-minute mental model (with diagrams)
- [daily-use.md](daily-use.md) — how to drive it day to day
- [examples.md](examples.md) — copy-paste prompts, simple → complex
- [privacy.md](privacy.md) — what stays on your machine
- [add-automation.md](add-automation.md) — add a new thing for Ernest to watch
