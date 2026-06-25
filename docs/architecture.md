# Architecture

Ernest on Claude Code is one evolving system with multiple surfaces.

## Surfaces

- Claude Code: reliable bootstrap/admin surface.
- Cowork: CEO-friendly desktop surface once verified.
- Telegram/Slack: optional chat mirror through the VPS brain when configured.

## Sources Of Truth

- Canonical memory and connector tokens: VPS Ernest brain when configured.
- Skill library and plugin behavior: git-versioned `ernest-cc`.
- Local mode memory and exported data: `~/ErnestVault` and `data/**`.

## Flow

1. Claude Code/Cowork loads `CLAUDE.md`, skills, commands, hooks, and MCP config.
2. A command or schedule invokes a skill.
3. Skills use the best available data source: VPS brain, local MCP connectors, then exported files under `data/**`.
4. Hooks block live external mutations.
5. Outputs are reminders or drafts.
6. Learning hook captures improvement candidates.
7. `/ernest-learn` turns candidates into reviewed proposals.

## Why Native Claude Code

The previous `ernest-agent` SDK port wrapped the same agent engine but reimplemented native Claude Code primitives. Native Claude Code gives us:

- skills
- hooks
- subagents
- MCP
- commands
- plugin distribution
- local headless `claude -p`
- Cowork compatibility path

The custom SDK app is no longer necessary for the MVP.
