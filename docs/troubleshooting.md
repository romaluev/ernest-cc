# Troubleshooting

## Install did not show a brief

Run from the `ernest-cc` directory:

```bash
./install.sh
```

You should see "Here is what needs you right now" and a brief summary. If not:

```bash
bash install.sh --health-only   # package intact?
~/.ernest-cc/bin/ernest start   # or: ernest start
```

## `install.sh --health-only` fails

Missing files mean the package is incomplete. Do not continue install.

## `ernest: command not found`

The installer links `ernest` into a PATH directory when installing to
`~/.ernest-cc`. If that failed, use the full path once:

```bash
~/.ernest-cc/bin/ernest start
```

Or add `~/.ernest-cc/bin` to your PATH.

## Nothing needs attention / empty brief

That means no enabled concern found a current issue on your data. Either your
inbox is clean, or live mail is not connected yet (Ernest is reading sample data
in `data/` until you connect Gmail).

Try a specific prompt from [examples.md](examples.md), e.g. "Which B2B intros
am I running without Manoj?"

## VPS mode asks for brain URL/token

Set `ERNEST_BRAIN_URL` and `ERNEST_BRAIN_TOKEN`, then rerun `./install.sh --mode vps`.
Local mode (`./install.sh`) works without VPS. See [vps-brain.md](vps-brain.md).

## Drafts are blocked

Expected if Ernest tried to send or mutate an external system. Ask for a draft or
reminder card instead. See [security.md](security.md).

## Update Ernest without losing your memory

```bash
git pull --ff-only && ./install.sh --refresh
```

## Cowork behaves differently

Use Claude Code as the reliable bootstrap surface. Same plugin; verify
connectors/hooks on your Cowork build.
