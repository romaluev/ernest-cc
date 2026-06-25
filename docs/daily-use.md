# Daily Use

## The one command

```bash
ernest start
```

It refreshes everything and prints what needs you today. If you only ever run
one command, run this. Everything below is optional depth.

Every step has two equivalent paths: the slash command (model-driven, connector
aware) and the engine command (deterministic, offline). Use whichever fits.

| Task | Slash command | Engine command |
| --- | --- | --- |
| Morning brief | `/ernest-brief` | `ernest brief` |
| Ambient watch | `/ernest-watch` | `ernest watch` |
| Draft replies | `/ernest-draft` or `draft these` | `ernest draft --concern <id>` |
| Add automation | `/ernest-new-automation` | `ernest new-automation --id <id> --playbook <p>` |
| Weekly learning | `/ernest-learn` | `ernest learn` |

## What `watch` covers

A single `ernest watch` (or `/ernest-watch`) runs every enabled concern and
writes one card per result to `00-Watch/`:

- B2B threads missing your collaborator (add-collaborator)
- candidates to assign reach-out (candidate-followup)
- important contacts you owe (account-followup-recovery, tier-scoped)
- email vs HubSpot list / Google Sheet gaps (list-sync)
- sourcing targets needing outreach (sourcing-pipeline)
- open/overdue tasks by owner (task-tracker)
- dropped follow-ups and inbound prospects

These are remind/assign cards — no drafts unless you ask.

## Morning

Run:

```text
/ernest-brief
```

Ernest returns the items needing CEO attention today. If nothing matters, it returns `[SILENT]`.

## During The Day

Ambient watch runs at 11:00 and 16:00 when scheduled. Manual run:

```text
/ernest-watch
```

Cards end with:

```text
Reply draft these when you want me to prepare actions.
```

## Drafting

To draft from a card:

```text
draft these
```

or:

```text
/ernest-draft card_id=<card-id>
```

Ernest prepares an approval batch. It does not send.

## Adding A New Automation

```text
/ernest-new-automation
```

Describe the recurring work in one sentence. Ernest will either configure an existing skill or propose a new one.

## Weekly Learning

```text
/ernest-learn
```

Ernest reviews recent learning candidates and proposes at most one improvement.
