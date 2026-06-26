# Security

Ernest's safety is enforced by a **deterministic gate** that runs before any tool
call (`hooks/pre_tool_use.py` → `ernest/gate.py`). It is not a prompt the AI can talk
its way around — it's code that blocks first.

## What the gate blocks (deny-by-default)

- **Live external actions** — sending email, posting to Slack, changing your CRM,
  paying, calendar invites, deleting. Blocked on **every** connector, including ones
  named by opaque id, and including actions hidden inside an "execute" wrapper. You
  get a draft for review instead.
- **Reading secrets** — `.env`, the token/credential files, `.ssh`, `.aws`, Ernest's
  own config — blocked even via the terminal.
- **Network egress in local mode** — web fetch/search and any external send/notify are
  off by default so nothing leaves the machine. Turn web on for a task with
  `ERNEST_ALLOW_WEB=1` when you actually need research.
- **Tampering with the guardrails** — the gate, hooks, tests, and audit log can be
  read but not written, so the self-improvement loop can never disarm its own safety.

What's always allowed: reading, searching, summarizing, writing reminder cards, and
preparing drafts.

## Prompt injection

If a malicious email or message says "send this now" or "ignore your rules," the gate
still blocks the live send — the decision is deterministic and independent of what the
model "decided." The worst case is a draft you can review. Reminder cards never carry
unsent draft bodies, so nothing sensitive is echoed back into ambient content.

## Approval levels

| Level | Examples | Who |
|---|---|---|
| L0 | read, search, classify, summarize, reminder cards | automatic |
| L1 | reversible internal memory/preference update | automatic, logged |
| L2 | external drafts, CRM-change proposals, outreach batches | **CEO approves** |
| L3 | money, legal, contracts, irreversible deletes, credentials, new permissions | **manual only** |

One bounded exception: a CRM "hygiene" job may auto-fix mechanical fields (company,
first/last name, title) — and only when it's explicitly armed, within a time window,
on an allowed field list. It ships **off**.

## Where your data lives

- **Local mode (default):** no tokens, no server, no network. See [privacy.md](privacy.md).
- **VPS mode (optional):** connector tokens live only on your server; the laptop holds
  one access key, locked to owner-only (`chmod 600`).

## Updates can't weaken this

Every auto-update runs a **gate self-test** (`python -m ernest.gate --selftest`) before
it's allowed to install. A version that tried to open a hole fails the test and is
rejected, then rolled back. See [updates.md](updates.md).

## Self-improvement safety

Ernest can propose new skills and tuning, but adoption is a reviewed change with a
rollback — it never auto-grants itself send rights, credentials, memory scope, or
money/legal authority.
