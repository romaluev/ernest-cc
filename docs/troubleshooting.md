# Troubleshooting

## `install.sh --health-only` fails

Run from the `ernest-cc` directory:

```bash
bash install.sh --health-only
```

Missing files mean the package is incomplete. Do not continue install.

## VPS mode asks for brain URL/token

Set:

```bash
ERNEST_BRAIN_URL="https://your-vps.example.com/mcp"
ERNEST_BRAIN_TOKEN="..."
```

Then rerun `./install.sh`.

## Claude cannot reach the brain

Check:

- VPN/firewall.
- Brain URL is reachable.
- Token is current.
- `mcp__ernest-brain__health` works.

Use local fallback if the brain is unavailable:

```bash
./install.sh --mode local
```

## Drafts are blocked

This is expected if Ernest tried to send or mutate an external system. Ask Ernest to create a draft or proposal instead.

## Watch returns `[SILENT]`

That means no enabled concern found a current issue. Run `/ernest-watch` with a narrower request if you expected something.

## Cowork behaves differently

Use Claude Code as the reliable admin/bootstrap surface. Cowork should use the same plugin and connectors, but connector/hook parity must be verified on the target build.
