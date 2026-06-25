# Daily Use

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
