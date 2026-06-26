# Privacy — what stays on your machine

Short version: **in the default setup, everything stays on your Mac. Nothing is sent
to any server, and no part of your data leaves the machine.**

## What "local-first" means here

| Thing | Where it lives (default) | Leaves your machine? |
|---|---|---|
| Your memory (company, contacts, preferences, notes) | On your Mac, as plain files | **No** |
| Reminder cards, drafts, briefs | On your Mac | **No** |
| Email / Slack / CRM you connect | Read live through your own accounts | Only between you and that app, as today |
| The AI model | Claude, via your existing Claude app | Your prompts go to Claude like any Claude chat |

There is no Ernest server in the default setup. Ernest is a local assistant.

## The guarantees, and how they're enforced

These aren't promises in a doc — they're enforced by a deterministic gate that runs
before any action:

- **No silent sending.** Ernest can never send an email, post to Slack, change your
  CRM, or pay anyone without you approving that exact action.
- **No secret reading.** Ernest is blocked from reading credential files (`.env`,
  tokens, SSH/AWS keys, its own config) — even via the terminal.
- **No quiet phone-home.** In local mode, web access is **off** by default, so nothing
  can be exfiltrated through a web request. (You can turn web on for a research task.)
- **Your data isn't mirrored.** If you ever add a server (optional, below), your app
  passwords/tokens live only there — never copied to your laptop, and vice versa.

## If you ever want 24/7 (optional)

A laptop can't watch your inbox while it's asleep. If you want overnight coverage,
you can add a private server ("the brain"). It's **opt-in and separate**:

- You choose it explicitly during setup. The default never uses it.
- Then your connector tokens live on that server (isolated), and your laptop holds
  only a single access key — not your Gmail/Slack/CRM passwords.
- You can detach anytime and go fully local again, with no data loss.

For an NDA-sensitive setup, the recommendation is simple: **stay local.** You lose
only overnight watching, which you can run on demand instead.

## Backups

Your memory is plain text, versioned over time, so you can see and roll back any
change. Nothing about backups sends your data anywhere unless you choose a server.
