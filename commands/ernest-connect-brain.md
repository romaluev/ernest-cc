# /ernest-connect-brain

Point THIS surface (Claude Code or Cowork) at the VPS brain so it shares ONE
memory, watch-card set, and draft store with the 24/7 Telegram/Slack Ernest. Use
this for the **CC+VPS** and **Cowork+VPS** combos. No terminal fiddling for the
CEO — you do it.

Run it:

```bash
ernest connect-brain --url https://<brain-host-or-tunnel>
```

That one command, idempotently:

1. Persists `mode: vps` + the brain URL to `connection.json` (durable across
   sessions — no `ERNEST_MODE` env var needed).
2. Registers the `ernest-brain` MCP server for the live agent. In Claude Code it
   runs `claude mcp add` for you (local scope). The bearer token is **never**
   written to disk or a command line — the header is stored as the placeholder
   `${ERNEST_BRAIN_TOKEN}`, which Claude expands from the environment at load.
3. Probes the brain's `/health` and reports reachable / offline.

Before/while connecting:

- The only secret needed is the bearer token, exported once as
  `ERNEST_BRAIN_TOKEN` in the shell (or the CEO's secrets file). Confirm it's set;
  if not, tell the CEO that one value is required and where to get it (whoever set
  up the VPS). Do not print or ask them to paste it into a file.
- If the brain URL is unknown, ask for it (or read a previously-persisted one).
- If `/health` is offline, the brain may not be deployed yet — point to
  `docs/plus-vps.md` (deploy with `adapters/vps/deploy-brain.sh`) and stop.

**Cowork (no terminal):** there's no `claude` CLI, so after persisting state, add
the connector once via **Settings → Connectors → Add custom (HTTP/MCP)** with the
brain URL and header `Authorization: Bearer <ERNEST_BRAIN_TOKEN>`. Walk the CEO
through that screen; everything else is automatic.

After connecting, confirm in one line (e.g. "Connected — shared brain online; your
laptop and phone now see the same memory and reminders"). Switch back any time
with `/ernest-go-local`.
