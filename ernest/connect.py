"""Connect a local surface (Claude Code / Cowork) to the VPS brain — or go back
to local-only — in ONE step, no terminal fiddling.

The two `+VPS` surface combos (CC+VPS, Cowork+VPS) need exactly two things to
work and stay working across sessions:

  1. The live agent must see the brain's MCP tools. Canonically that's
     `claude mcp add --transport http ernest-brain <url> --header "...Bearer ..."`.
  2. The engine must know it's in VPS-brain mode so `ernest doctor` / briefs read
     the shared brain, not local-only — durably, without an `ERNEST_MODE` env var.

`connect()` does both; `go_local()` reverses both. The bearer token is NEVER
written to disk or passed on a command line: the MCP header is stored as the
literal placeholder `${ERNEST_BRAIN_TOKEN}`, which Claude expands from the
environment at load time. connection.json is per-machine (gitignored), and the
engine refuses to modify a *git-tracked* `.mcp.json`, so a committed template is
never mutated — the live agent is wired via `claude mcp add` instead.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

from . import config

DEFAULT_NAME = "ernest-brain"
DEFAULT_TOKEN_ENV = "ERNEST_BRAIN_TOKEN"


def resolve_url(cfg: config.Config, explicit: str = "") -> str:
    if explicit and explicit.strip():
        return explicit.strip().rstrip("/")
    env = os.environ.get("ERNEST_BRAIN_URL", "").strip()
    if env:
        return env.rstrip("/")
    return str(config.read_connection(cfg.profile_dir).get("brain_url", "")).rstrip("/")


def health_probe(url: str, timeout: float = 4.0) -> Tuple[bool, str]:
    if not url:
        return False, "no brain URL"
    try:
        with urllib.request.urlopen(url + "/health", timeout=timeout) as r:  # noqa: S310
            return (200 <= r.status < 300), f"HTTP {r.status}"
    except Exception as exc:  # noqa: BLE001 — health is advisory, never fatal
        return False, f"{type(exc).__name__}"


def _header_placeholder(token_env: str) -> str:
    # Literal — Claude Code expands ${VAR} from the environment at load time.
    return f"Bearer ${{{token_env}}}"


def _is_git_tracked(path: Path) -> bool:
    """True if `path` is a file tracked by git — we must not rewrite a committed
    `.mcp.json` template (the live agent is wired via `claude mcp add` instead)."""
    try:
        r = subprocess.run(["git", "ls-files", "--error-unmatch", path.name],
                           cwd=str(path.parent), capture_output=True, text=True, check=False)
        return r.returncode == 0
    except OSError:
        return False


def write_mcp_entry(cfg: config.Config, name: str, url: str, token_env: str) -> bool:
    """Merge the brain server into the profile .mcp.json (token as placeholder).

    Returns True if written. Skips (returns False) when the target is git-tracked,
    so a committed template is never mutated."""
    path = cfg.mcp_file
    if path.is_file() and _is_git_tracked(path):
        return False
    data: dict = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8")) or {}
        except (OSError, ValueError):
            data = {}
    servers = data.setdefault("mcpServers", {})
    servers[name] = {
        "type": "http",
        "url": url,
        "headers": {"Authorization": _header_placeholder(token_env)},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return True


def remove_mcp_entry(cfg: config.Config, name: str) -> str:
    """Remove the brain server from the profile .mcp.json. Returns 'removed',
    'absent', or 'skipped' (git-tracked template left untouched)."""
    path = cfg.mcp_file
    if not path.is_file():
        return "absent"
    if _is_git_tracked(path):
        return "skipped"
    try:
        data = json.loads(path.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return "absent"
    servers = data.get("mcpServers", {})
    if name not in servers:
        return "absent"
    del servers[name]
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return "removed"


def set_connection(cfg: config.Config, mode: str, brain_url: str = "") -> None:
    """Persist durable mode (+url). Never stores a secret."""
    cfg.profile_dir.mkdir(parents=True, exist_ok=True)
    payload = {"mode": mode}
    if brain_url:
        payload["brain_url"] = brain_url.rstrip("/")
    cfg.connection_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _claude_cli(*args: str) -> Optional[Tuple[int, str]]:
    """Run the `claude` CLI if present; None if it isn't on PATH (e.g. Cowork), if
    ERNEST_NO_CLI is set (CI/tests/headless — don't mutate live MCP config), or if
    the exec fails (TOCTOU/perms/arch) — callers fall back to printed guidance."""
    if os.environ.get("ERNEST_NO_CLI", "").strip():
        return None
    if not shutil.which("claude"):
        return None
    try:
        proc = subprocess.run(["claude", *args], text=True, capture_output=True, check=False)
    except OSError:
        return None
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def connect(cfg: config.Config, url: str = "", *, name: str = DEFAULT_NAME,
            token_env: str = DEFAULT_TOKEN_ENV) -> int:
    target = resolve_url(cfg, url)
    if not target:
        print("Need the brain URL. Ask the person who set up the VPS, then run:")
        print("  ernest connect-brain --url https://<brain-host-or-tunnel>")
        return 2
    if not target.lower().startswith(("http://", "https://")):
        print(f"Brain URL must start with http(s):// — got '{target}'.")
        return 2

    # 1) Persist durable engine-side mode (survives sessions; no env needed).
    set_connection(cfg, "vps", target)
    # 2) Reference profile .mcp.json (token stays a placeholder, no secret on disk;
    #    a git-tracked template is left untouched).
    wrote = write_mcp_entry(cfg, name, target, token_env)

    # 3) Register with the live agent. CC has the `claude` CLI; Cowork uses its UI.
    # Idempotent + scope-explicit: clear any prior local entry first, then add at
    # local scope (never touches a committed project .mcp.json template).
    _claude_cli("mcp", "remove", "-s", "local", name)
    cli = _claude_cli("mcp", "add", "-s", "local", "--transport", "http", name, target,
                      "--header", f"Authorization: {_header_placeholder(token_env)}")
    print(f"Connected this surface to the VPS brain ({target}).")
    print(f"mode: vps  →  {cfg.connection_file}")
    print(f"mcp:  {name}  →  {cfg.mcp_file}" if wrote
          else f"mcp:  {name}  →  left the git-tracked template untouched (using claude CLI / connection.json)")
    if cli is not None:
        rc, _out = cli
        print("claude CLI: registered ✓" if rc == 0 else
              "claude CLI present but `mcp add` returned nonzero — re-run /ernest-connect-brain or add it via the Connectors UI.")
    else:
        print("No `claude` CLI here (Cowork?). Add the connector once via the UI:")
        print("  Settings → Connectors → Add custom (HTTP/MCP)")
        print(f"    URL: {target}")
        print(f"    Header: Authorization: Bearer <your {token_env}>")

    ok, detail = health_probe(target)
    print(f"brain health: {'reachable ✓' if ok else f'NOT reachable ({detail})'}"
          + ("" if ok else " — the brain may not be deployed yet (see docs/plus-vps.md)."))
    print(f"\nMake sure {token_env} is exported in your shell (it never gets written to disk).")
    print("Switch back anytime with `ernest go-local` (or /ernest-go-local).")
    return 0


def go_local(cfg: config.Config, *, name: str = DEFAULT_NAME) -> int:
    set_connection(cfg, "local")
    status = remove_mcp_entry(cfg, name)
    cli = _claude_cli("mcp", "remove", "-s", "local", name)
    print("This surface is now LOCAL-only — local memory, local connectors, data/ exports.")
    print(f"mode: local  →  {cfg.connection_file}")
    label = {"removed": "removed", "absent": "not present",
             "skipped": "git-tracked template left untouched"}[status]
    print(f"mcp:  {name} {label}")
    if cli is not None:
        rc, _out = cli
        if rc == 0:
            print("claude CLI: connector removed ✓")
        else:
            # Don't silently claim on-device-only while the agent still has it.
            print(f"⚠ claude CLI: could not remove '{name}' — it may still be registered. "
                  f"Remove it via the Connectors UI, or `claude mcp remove -s local {name}`.")
    print("Reconnect anytime with `ernest connect-brain` (or /ernest-connect-brain).")
    return 0
