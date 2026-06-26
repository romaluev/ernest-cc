# Troubleshooting

## Install did not show a brief

```bash
./install.sh
```

You should see "Here is what needs you right now." If not:

```bash
bash install.sh --health-only
ernest start
```

## `ernest: command not found`

Use once:

```bash
~/.ernest-cc/bin/ernest start
```

Or add `~/.ernest-cc/bin` to PATH. The installer links `ernest` into a PATH
directory when installing to `~/.ernest-cc`.

## Empty brief / nothing needs attention

Either your data is clean, or Ernest is still on sample/export files in `data/`
(not live mail). Connect native MCP — see [connectors.md](connectors.md) — or
drop your exports into `data/mail/`, `data/hubspot/`, etc.

Try a specific prompt from [examples.md](examples.md).

## Health check fails

Run `bash install.sh --health-only` from the repo root. Missing files = incomplete package.

## VPS mode needs URL/token

Set `ERNEST_BRAIN_URL` and `ERNEST_BRAIN_TOKEN`, rerun `./install.sh --mode vps`.
Or stay on local: `./install.sh` (default).

## Drafts blocked

Expected when Ernest tried to send or mutate an external system. Ask for a
reminder or draft instead. See [security.md](security.md).

## Update without losing memory

```bash
git pull --ff-only && ./install.sh --refresh
```

## Something's broken or a tool is missing — let Ernest fix it

Ernest is built to repair and extend itself. Run:

```bash
ernest doctor
```

It prints a `diagnostics:` block with a `fix:` for each issue. For an automatic
pass, in Claude run:

```text
/ernest-doctor
```

Ernest will diagnose, research the right tool/MCP server on the web, apply safe
in-workspace fixes, and propose anything that needs your approval (connectors,
credentials, installs). It verifies with `ernest doctor` and can make a recurring
fix permanent as a skill or automation.

## Change the ICP / grading / talent pool

Criteria are living config — not hardcoded. Edit `data/grading/b2b-rubric.json`
or `data/grading/talent-rubric.json` (e.g. the talent `pool`, company lists,
Tier-1 countries), or just tell Ernest "change our talent focus to X". Re-run:

```bash
ernest grade
```

## Cowork differs from Claude Code

Use Claude Code as the bootstrap surface. Same plugin; verify connectors on your build.
