# Daily Use

Every step has two equivalent paths: the slash command (model-driven, connector
aware) and the engine command (deterministic, offline). Use whichever fits.

| Task | Slash command | Engine command |
| --- | --- | --- |
| Morning brief | `/ernest-brief` | `ernest brief` |
| Ambient watch | `/ernest-watch` | `ernest watch` |
| Draft replies | `/ernest-draft` or `draft these` | `ernest draft --concern <id>` |
| Add automation | `/ernest-new-automation` | `ernest new-automation --id <id> --playbook <p>` |
| Weekly learning | `/ernest-learn` | `ernest learn` |

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
