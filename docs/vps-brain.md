# VPS Brain

The VPS brain is the remote single source of truth for Ernest memory and heavy connectors.

## Why Keep It

- Connector tokens stay on the VPS.
- The CEO's laptop does not store Gmail/HubSpot/Slack secrets.
- Telegram/Slack can keep working through the same brain.
- Local Claude Code/Cowork can be a thin surface.

## Required MCP Contract

See `brain/ernest-brain.contract.json`.

Minimum tools:

- `health`
- `search_memory`
- `write_memory`
- `list_watch_cards`
- `write_watch_card`
- `search_mail`
- `create_mail_draft`
- `search_hubspot`
- `search_slack`

## Health Check

The brain should return:

```json
{
  "status": "ok",
  "mode": "vps-brain",
  "draft_first_gate": "enabled",
  "connectors": {
    "mail": "connected",
    "hubspot": "connected",
    "slack": "connected",
    "calendar": "connected"
  }
}
```

## Auth

Local Claude Code connects with:

```bash
claude mcp add --transport http ernest-brain "$ERNEST_BRAIN_URL" \
  --header "Authorization: Bearer $ERNEST_BRAIN_TOKEN"
```

The installer writes this config. The CEO should not.
