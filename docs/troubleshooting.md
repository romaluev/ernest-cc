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

## Cowork differs from Claude Code

Use Claude Code as the bootstrap surface. Same plugin; verify connectors on your build.
