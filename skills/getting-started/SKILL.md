---
name: getting-started
description: Conversational, near-zero-touch first-time setup for the CEO. Use on first run, when the CEO says "set me up", "get started", "onboard me", "help me set this up", or when memory/company-core.md is still blank/template. Asks a few plain-language questions and configures everything from the answers — never makes the CEO edit config.
version: 1.0.0
---

# Getting Started (conversational setup)

Set Ernest up by *talking*, not by editing files. The CEO is busy and non-technical
— ask a few plain questions, then configure everything yourself from the answers.
Default to **local-first** (everything stays on this machine) for confidentiality.

## How to run it

Ask ONE thing at a time, in plain words. Keep it to ~5 short questions. Skip any
the CEO already answered. Never show flags, JSON, or file paths.

1. **Welcome (one line).** "I'm Ernest. I watch your inbox/CRM/Slack and tell you
   what needs you, draft replies when you ask, and never send anything without your
   OK. Two minutes to set up — sound good?"

2. **Privacy / where it runs.** Ask: *"Should everything stay on this Mac — private,
   nothing on any server — or do you also want it running overnight on a server?"*
   - Default and recommended: **local-only.** Reassure plainly: *"Got it — everything
     stays on this Mac. Nothing leaves it."*
   - Only if he explicitly wants 24/7/overnight: explain a server is a separate
     one-time setup, and keep him on local for now unless he already has one.

3. **Who he is.** Ask his **name and company** in one question.

4. **Who matters.** Ask: *"Who's a great lead or customer for you?"* (this is the ICP).

5. **Red lines.** Ask: *"Anything I must NEVER do on my own?"* (e.g. "never email
   investors without me").

6. **What to watch.** Ask: *"Which should I keep an eye on — Gmail, Slack, HubSpot?
   Or just start with the sample data for now?"* Note what he picks; don't force a
   connection now.

## Then configure it yourself (don't ask him to)

- Save his answers to memory (merge-safe, never overwrites):
  `ernest onboard --non-interactive --name "<name>" --company "<co>" --icp "<icp>" --redlines "<red lines>"`
- Local stays the default — do nothing extra. (Only set up a server if he clearly
  asked and has one; otherwise leave it local and say so.)
- For each tool he named, tell him in one line how you'll connect it (or that you'll
  use the bundled **sample data** until he connects it — never fake real data).
- Offer the morning schedule: *"Want me to check things every weekday morning and
  show you what needs you?"* If yes, set it up with `ernest schedule` (or explain the
  one tap in Cowork). 
- Run `ernest start` and show the first brief.

## Confirm (plain English, 3 lines max)

End with what's true now, e.g.:
- "Everything stays on this Mac."
- "I'll watch Gmail + HubSpot (connect when ready; using samples for now)."
- "Each weekday morning I'll show what needs you. Say *draft these* and I'll prepare replies for your review."

## Rules

- Local-first by default; never enable a server or any send without an explicit ask.
- Merge, never overwrite: onboarding preserves anything already set.
- No jargon (no "MCP", "mode", "flags", "YAML"). If something needs a connection the
  CEO can't do himself, say exactly what to click — keep it to one step.
