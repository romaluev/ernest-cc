---
name: call-coaching
description: Turn recorded calls into coaching and a reusable best-practices library. Use when the CEO or a rep asks to review calls, "what worked / what didn't", objection handling, talk-track patterns, win/loss themes, or wants to build a playbook from real calls. Read-only analysis; any write to Notion/Slack is draft-first.
version: 1.0.0
---

# Call Coaching

Northwind has call recording (Fireflies) but no coaching layer yet. This skill
mines calls for patterns and proposes a best-practices library — it does not
grade people punitively; it extracts what works and turns it into reusable plays.

## Inputs

```yaml
scope: "last_7d"     # window, a rep, an account, or a single call
focus: "all"         # discovery | objections | pricing | next-steps | win-loss
```

## Data sources (read-only; swappable)

- **Fireflies** (or Gong) MCP — transcripts, summaries, action items, talk ratios.
- **HubSpot** — outcome of the deal tied to each call (won/lost/stage move).
- **Notion** MCP — existing playbook/positioning to compare against and extend.
- Export fallback: `data/calls/**`, `data/hubspot/**`, `data/notion/**`.

Read full transcripts, not just auto-summaries, before drawing conclusions.

## Run sequence

1. Pull calls in `scope`; read transcripts + outcomes.
2. Extract patterns by `focus`: what advanced deals, objections + the responses
   that worked, where momentum stalled, missed next-steps.
3. Cross-reference outcomes (win/loss) so advice is grounded in results, not vibes.
4. Propose 3–7 reusable plays (objection → proven response; strong discovery
   questions; effective framing) for the best-practices library.
5. Offer to save the library to Notion and share a coaching note in Slack —
   **draft-first**, never auto-posted.

## Output

Chat (house format): **Bottom line** (the one habit that most moves outcomes),
then the top plays as bullets, then **Read more →** the full coaching write-up
(`ernest render`). Per rep, keep it constructive: strength, one fix, one play.

## Rules

- Read-only by default. Saving to Notion or posting to Slack is a draft proposal for approval.
- Ground every recommendation in a specific call + outcome; quote sparingly, cite the call.
- No surveillance framing. This is enablement: capture what works and spread it.
- Flag anything sensitive (compensation, PIP-style judgments) for the CEO, don't act on it.
