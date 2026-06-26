# Ernest — documentation

Ernest is a draft-first chief-of-staff for a busy CEO. It watches your inbox, CRM, and
Slack, tells you what needs you, drafts replies and outreach when you ask, and never
sends anything on its own. Local-first: your memory stays on your machine.

## Start here

| If you want to… | Read |
|---|---|
| **See what's possible** (vision, diagrams, ideas to try) | [vision.md](vision.md) |
| **Get started** (in Claude, no terminal) | [quickstart.md](quickstart.md) |
| **Understand how it works** (2 min, with diagrams) | [how-it-works.md](how-it-works.md) |
| **Use it day to day** | [daily-use.md](daily-use.md) |
| **See example prompts** (simple → complex) | [examples.md](examples.md) |

## Reference

| Doc | Purpose |
|---|---|
| [privacy.md](privacy.md) | What stays on your machine (and what doesn't) |
| [updates.md](updates.md) | How updates work — one-tap, validated, auto-rollback |
| [connectors.md](connectors.md) | Connect Gmail / Slack / CRM (native MCP, not Composio) |
| [add-automation.md](add-automation.md) | Add a new thing for Ernest to watch |
| [security.md](security.md) | The safety gate and approval levels |
| [troubleshooting.md](troubleshooting.md) | When something looks off |
| [architecture.md](architecture.md) | How the pieces fit (for maintainers) |
| [vps-brain.md](vps-brain.md) | Optional 24/7 server — skip unless you need overnight |

## The 30-second version

1. Install `ernest-cc` in Claude and run `/ernest-setup` (or `./install.sh` in a terminal).
2. Ask **"what needs me today?"**
3. Reply **"draft these"** to get replies prepared for review. You approve every send.
