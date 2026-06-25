---
name: slack-task-tracker
description: Transparent company task tracking from Slack. Surfaces open and overdue tasks by owner so nothing silently stalls. Remind/assign only; the first step toward a full Slack-driven task system.
version: 1.0.0
---

# Slack Task Tracker

Goal: make task ownership across the company transparent, driven from Slack.
Anyone flags work; Ernest tracks who owns what and what is overdue.

## Parameters

```yaml
source: "data/slack/tasks.csv"   # exported/synced tasks
```

Task rows: `task,owner,status,due,source`. `status` is `open | done | closed`.

## Watch Half

1. Read tasks (Slack MCP when connected -> `data/slack/tasks.csv` offline).
2. Surface every task not `done`/`closed`, flagging overdue ones.
3. Write one card grouped by state: overdue first, then open, with the owner.

No drafts. The action is "track to done; nudge the owner".

## Deterministic baseline

`ernest watch` runs this for the `slack-task-tracking` concern over the exported
tasks file, with no model and no connectors.

## Live Slack (connector-backed next step)

With a Slack MCP, Ernest can:

- turn a message or emoji reaction into a tracked task,
- post a daily "open/overdue by owner" summary to a channel (CEO-approved),
- nudge owners on stalled tasks.

Creating tasks from Slack and posting to channels are external actions and stay
approval-gated. This skill starts as read/track-only.

## When Not To Use

Not a replacement for a full project tracker. This is lightweight, transparent
ownership and overdue surfacing.
