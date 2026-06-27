# /ernest-go-local

Disconnect this surface from the VPS brain and run **local-only** — local memory,
local MCP connectors, and `data/` exports. The reverse of `/ernest-connect-brain`.
Use it when the CEO wants everything on-device (NDA-sensitive work), the VPS is
down, or for a clean local demo.

Run it:

```bash
ernest go-local
```

That one command:

1. Sets `mode: local` in `connection.json` (durable).
2. Removes the `ernest-brain` MCP server from the profile `.mcp.json` and, in
   Claude Code, runs `claude mcp remove -s local ernest-brain` for the live agent.
3. Leaves the brain itself untouched on the VPS — only this surface disconnects.

Notes:

- Nothing is lost: local memory and `data/` keep working immediately; the durable
  cross-machine record is git on the state repo, not the live connection.
- **Cowork:** also remove the custom connector via **Settings → Connectors** if it
  was added there.

Confirm in one line (e.g. "Now local-only — nothing leaves this machine").
Reconnect any time with `/ernest-connect-brain`.
