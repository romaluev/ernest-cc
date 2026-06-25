# Architecture

Ernest on Claude Code is one evolving system with multiple surfaces.

## Surfaces

- Claude Code: reliable bootstrap/admin surface.
- Cowork: CEO-friendly desktop surface once verified.
- Telegram/Slack: optional chat mirror through the VPS brain when configured.

## Two Layers

- **Engine** (`ernest/`): a pure standard-library Python package. The CEO runs
  **`ernest start`** (watch + brief). Other commands (`draft`, `new-automation`,
  `learn`) are optional. Prompt examples: `docs/examples.md`.
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
2. A schedule or `ernest start` runs the engine; Claude invokes skills when the CEO asks.
3. Work uses: VPS brain (optional) → native MCP connectors → exported files in `data/**`. No Composio. See `docs/connectors.md`.
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
