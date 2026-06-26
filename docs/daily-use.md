# Daily Use

## One command

```bash
ernest start
```

Watch + brief. Cards land in `~/ErnestVault/Ernest/00-Watch/`, and a clean
**digest** (the "Read more" view) in `00-Daily/digest--<date>.html`. Nothing sends.

Prompts for Claude: [examples.md](examples.md).

## Readable, adaptive answers

In Claude, answers are **short by default** — Bottom line, a few action bullets,
then a **Read more →** link to the digest. Tell Ernest what you like and it
remembers (`memory/preferences.md`): "too long, 4 bullets", "prefer PDF",
"hide trash tier". You rarely need commands — just talk to it.

## What runs automatically

Each `start` evaluates every enabled concern in `memory/standing-concerns.md`:

| Type | Example card |
|---|---|
| Follow-ups | Threads you owe |
| VIP recovery | Important-tier slips |
| Collaborator coverage | Threads missing a teammate |
| Candidate assignment | Inbox hires to route |
| List sync | Email vs CRM or sheet gaps |
| Sourcing | Pipeline targets to contact |
| Task tracking | Open/overdue by owner |
| Inbound prospects | Partnership/sales leads waiting |

All are remind/assign unless you ask for drafts.

## Claude vs terminal

| Task | In Claude | Terminal |
|---|---|---|
| Daily | "What needs me today?" / `/ernest-brief` | `ernest start` |
| Clean / shareable view | "show today's digest" | `ernest render --open` (`--pdf`) |
| Tune answers | "too long, prefer PDF" | `ernest feedback "..."` / `ernest prefs` |
| Draft (optional) | `draft these` / `/ernest-draft` | `ernest draft --concern <id>` |
| New automation | `/ernest-new-automation` | `ernest new-automation ...` |
| Learning | `/ernest-learn` | `ernest learn` |

Use Claude when you want live mail/CRM search. Use `ernest start` when exports
or sample data are enough.

## First-time setup

Run **`/ernest-setup`** in Claude (or `ernest onboard` in the terminal). Ernest asks a
few plain questions and configures itself — local-first, nothing sent. Re-running it
never overwrites what you've already set.

## Scheduling

Run **`ernest schedule`** once. Ernest then prepares your morning brief at 8:00 and
checks for updates at 7:30, every day — no open Claude session required, nothing sent.
Remove it anytime with `ernest schedule --remove`. (Under the hood it installs a
launchd agent on macOS, or use `crontab ~/.ernest-cc/crontab.example` elsewhere.)

## Connectors

Optional. Native MCP or file exports — not Composio. Details: [connectors.md](connectors.md).
