# Architecture

Ernest on Claude Code is one evolving system with multiple surfaces.

## Surfaces

- Claude Code: reliable bootstrap/admin surface.
- Cowork: CEO-friendly desktop surface once verified.
- Telegram/Slack: optional chat mirror through the VPS brain when configured.

## Two Layers

- **Engine** (`ernest/`): a pure standard-library Python package exposing
  `ernest <doctor|onboard|watch|brief|draft|new-automation|learn>`. It is
  deterministic and runs with no model and no connectors, reading exported data
  under `data/**`. This is what makes the system verifiable end-to-end.
- **Claude layer** (`CLAUDE.md`, skills, commands, subagents): the
  natural-language interface. It reasons over live connectors/VPS brain when
  available and falls back to the engine's deterministic output otherwise.

The same `hooks/gate.py` logic (in `ernest/gate.py`) guards both layers.

## Sources Of Truth

- Canonical memory and connector tokens: VPS Ernest brain when configured.
- Skill library and plugin behavior: git-versioned `ernest-cc`.
- Local mode memory and exported data: `~/ErnestVault` and `data/**`.

## Flow

1. Claude Code/Cowork loads `CLAUDE.md`, skills, commands, hooks, and MCP config.
2. A command or schedule invokes a skill, or the engine runs headless (e.g. cron `ernest watch`).
3. Work uses the best available data source: VPS brain, local MCP connectors, then exported files under `data/**`.
4. Hooks block live external mutations; drafts are written, never sent.
5. Outputs are reminder cards (`00-Watch/`), briefs (`00-Daily/`), and drafts (`00-Drafts/`).
6. The Stop hook captures improvement candidates to `logs/learning-proposals.jsonl`.
7. `ernest learn` / `/ernest-learn` turns candidates into reviewed, approval-gated proposals.

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
