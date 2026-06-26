# VPS Brain (optional)

The VPS brain is an **optional** always-on server that holds Ernest's memory and connector tokens in one place, so a 24/7 surface (Telegram/Slack) and the CEO's laptop share the exact same state.

You do not need it. The default install is **local-only** — everything runs on the laptop. Reach for the brain only when you want Ernest reachable overnight or from more than one surface.

## Why run it

- **Tokens stay on the server.** Gmail / HubSpot / Slack credentials live only on the VPS. The laptop holds just one bearer token to reach the brain — nothing else.
- **One shared state.** The brain reads and writes the *same* markdown memory and reminder ("watch") cards the local engine uses, so a Telegram reminder and a Claude Code session never disagree. (Durable sync between machines is git on the state repo; the brain is the live API over it.)
- **Thin laptop.** Claude Code / Cowork stays a lightweight front end.

## What it is allowed to do — draft-first by construction

The brain is safe by design, not by policy text. Its contract exposes **no send, post, publish, or live-CRM-write tool at all**. The only things it can do:

- read memory, mail threads, Slack threads, HubSpot;
- write **internal** memory and remind-only watch cards;
- create **drafts** (never sends).

Two extra backstops, both in `brain/brain_core.py`:

- Any tool name outside the contract is refused.
- Connector reads and `create_mail_draft` are additionally routed through the same deterministic gate the laptop uses (`ernest/gate.py`), so a future mis-added mutating tool is blocked identically on the VPS and the laptop.

## The MCP contract

The full, authoritative contract is `brain/ernest-brain.contract.json`. It defines **11 tools**:

| Tool | What it does |
|---|---|
| `health` | Status, mode, draft-first flag, connector states |
| `search_memory` | Search canonical memory (scoped, with source refs) |
| `write_memory` | Append an approved internal memory note (no permission escalation) |
| `list_watch_cards` | List recent reminder cards by window / concern / id |
| `write_watch_card` | Write a remind-only card (no external draft bodies) |
| `search_mail` | Find mail thread candidates |
| `read_mail_thread` | Read **every** message in a mail thread by id |
| `create_mail_draft` | Create a mail draft for approval — never sends |
| `search_hubspot` | Search contacts / companies / deals / owners / activities |
| `search_slack` | Find Slack channel / thread candidates |
| `read_slack_thread` | Read **every** message in a Slack thread or DM |

`search_*` returns candidates; always follow with the matching `read_*_thread` to ground a draft in full history (Ernest's house rule: read the whole thread before drafting).

> **Reference implementation note.** The bundled brain wires the connector reads (`search_mail`, `read_mail_thread`, `search_hubspot`, `search_slack`, `read_slack_thread`) to native MCP on a real VPS. With nothing wired, they fall back to `data/<tool>.json` exports if present, otherwise return `status: "needs_config"` — they never fabricate results.

## How the pieces fit

```mermaid
flowchart LR
  subgraph Laptop["CEO laptop (holds only a bearer token)"]
    cc["Claude Code / Cowork"]
  end
  subgraph VPS["VPS brain (holds all connector tokens)"]
    srv["brain.server (HTTP MCP, bearer-auth)"]
    mem["Memory + watch cards + drafts"]
    srv --- mem
  end
  subgraph Ext["External systems"]
    mail["Gmail"]
    hub["HubSpot"]
    slack["Slack"]
    cal["Calendar"]
  end
  tg["Telegram / Slack 24/7 surface"]

  cc -->|"Authorization: Bearer TOKEN"| srv
  tg --> srv
  srv -->|"read / draft only"| mail
  srv -->|"read only"| hub
  srv -->|"read only"| slack
  srv -->|"read only"| cal

  classDef boundary fill:#1f2937,stroke:#9ca3af,color:#f9fafb
  class VPS,Laptop boundary
```

The dashed trust boundary is the point: secrets never cross to the laptop, and the brain can only read or draft.

## Run the brain on the VPS

Stdlib-only Python — no dependencies to install. Set a strong bearer token and start it:

```bash
ERNEST_BRAIN_TOKEN="$(openssl rand -hex 32)" \
ERNEST_PROFILE_DIR="$HOME/.ernest-cc" \
  python3 -m brain.server --host 127.0.0.1 --port 8787
```

- Binds to `127.0.0.1:8787` by default. Put it behind a TLS reverse proxy (e.g. nginx/Caddy) and expose **only** the HTTPS endpoint publicly.
- **Always set `ERNEST_BRAIN_TOKEN`.** With no token the server runs **open** (it prints `OPEN (no ERNEST_BRAIN_TOKEN set)` and accepts unauthenticated calls) — fine for local dev, never for a public VPS.
- A plain `GET /health` (or `/healthz`) returns `{"status":"ok","service":"ernest-brain"}` for load balancers and `ernest doctor`.

### Connector states in `health`

`health` reports each connector as `connected` only when its env var is set on the VPS, otherwise `missing` (the contract's full enum is `connected | missing | needs_auth`):

```bash
ERNEST_CONN_MAIL=1 ERNEST_CONN_HUBSPOT=1 ERNEST_CONN_SLACK=1 ERNEST_CONN_CALENDAR=1 \
  python3 -m brain.server --port 8787
```

A healthy response then looks like:

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

## Connect the laptop

Run the installer in VPS mode with the URL and token. **The installer writes the config — the CEO never edits it.**

```bash
ERNEST_BRAIN_URL="https://brain.example.com" \
ERNEST_BRAIN_TOKEN="the-same-token-as-the-server" \
  ./install.sh --mode vps
```

This writes `~/.ernest-cc/.mcp.json` pointing Claude Code at the brain over authenticated HTTP, and `chmod 600`-locks both `.mcp.json` and the `env` file so only the owner can read the token:

```json
{
  "mcpServers": {
    "ernest-brain": {
      "type": "http",
      "url": "https://brain.example.com",
      "headers": { "Authorization": "Bearer the-same-token-as-the-server" }
    }
  }
}
```

If you ever need to wire it by hand (the installer is the supported path), the equivalent one-liner is:

```bash
claude mcp add --transport http ernest-brain "$ERNEST_BRAIN_URL" \
  --header "Authorization: Bearer $ERNEST_BRAIN_TOKEN"
```

Missing URL or token? The installer stops and tells you exactly what to set:

```
VPS mode selected.
Set ERNEST_BRAIN_URL and ERNEST_BRAIN_TOKEN, then rerun:
  ERNEST_BRAIN_URL=https://... ERNEST_BRAIN_TOKEN=... ./install.sh
```

(See `docs/troubleshooting.md` → "VPS mode needs URL/token".)

## Verify it's working

```bash
# From the laptop, against the running brain:
curl -s -X POST "$ERNEST_BRAIN_URL" \
  -H "Authorization: Bearer $ERNEST_BRAIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"health","arguments":{}}}'
```

Expect `mode: vps-brain` and `draft_first_gate: enabled` in the result. A wrong or missing token returns HTTP 401 `unauthorized`. The bundled test `tests/test_brain.py` exercises the full lifecycle (auth, memory/watch/draft sync, draft-first enforcement) if you want an automated check.

## Going back to local-only

Re-run `./install.sh` with no `--mode vps` (local is the default). The installer rewrites `.mcp.json` to use the local memory server and drops the brain entry — your memory and data are preserved.
