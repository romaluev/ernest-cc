# Daily Use

## The one command

```bash
ernest start
```

It refreshes everything and prints what needs you today. If you only ever run
one command, run this.

**Prompts for Claude:** see [examples.md](examples.md) — simple one-liners and
complex workflows mapped to your real use-cases (Manoj on B2B, Alua/Limon
candidates, Nubank, Korea sync, press sheet, sourcing, Slack tasks).

## Optional depth

| Task | Say in Claude | Terminal (optional) |
|---|---|---|
| Daily brief + watch | "What needs me today?" or `/ernest-brief` | `ernest start` |
| Draft replies (optional) | `draft these` or `/ernest-draft` | `ernest draft --concern <id>` |
| Add automation | `/ernest-new-automation` | `ernest new-automation ...` |
| Weekly learning | `/ernest-learn` | `ernest learn` |

## What runs on every `start`

Behind the scenes, Ernest checks all enabled concerns and writes cards to
`~/ErnestVault/Ernest/00-Watch/`:

- B2B threads missing your collaborator (Manoj)
- B2B candidates to assign (Alua/Limon)
- important contacts you owe (VIP/investor)
- email vs HubSpot list / Google Sheet gaps (Korea, press)
- sourcing targets needing outreach
- open/overdue Slack tasks by owner
- dropped follow-ups and inbound prospects

These are **remind/assign cards** — no drafts unless you ask.

## Scheduling (hands-off)

Cron/launchd templates in `~/.ernest-cc/` run `ernest start` (or `ernest brief` /
`ernest watch`) on a schedule with no Claude session open. See
`crontab.example` and `launchd.example.plist`.

## When you want drafts

Only if you explicitly want message text prepared. Ernest never sends.

```text
draft these
```

```text
/ernest-draft concern=important-followups
```

## Adding a new automation

One sentence in Claude:

```text
/ernest-new-automation
Every Friday check investor follow-ups. Remind only.
```

Or see [add-automation.md](add-automation.md) and [examples.md](examples.md).

## Weekly learning

```text
/ernest-learn
```

Ernest surfaces one improvement proposal. Nothing changes until you approve it.
