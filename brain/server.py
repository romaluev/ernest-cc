"""Ernest brain MCP server — Streamable-HTTP/JSON-RPC, stdlib only.

Implements the JSON-RPC methods Claude Code's `--transport http` MCP client uses
(initialize, tools/list, tools/call, ping) over the brain contract, with bearer
auth. App/connector tokens live ONLY here on the VPS; the laptop holds just the
bearer. Run:

    ERNEST_BRAIN_TOKEN=secret ERNEST_PROFILE_DIR=~/.ernest-cc \\
      python3 -m brain.server --host 127.0.0.1 --port 8787

Connect the laptop:

    claude mcp add --transport http ernest-brain http://HOST:PORT \\
      --header "Authorization: Bearer $ERNEST_BRAIN_TOKEN"
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brain.brain_core import Brain, CONTRACT_TOOLS  # noqa: E402

_CONTRACT_PATH = ROOT / "brain" / "ernest-brain.contract.json"


def _tool_specs():
    descriptions = {}
    try:
        data = json.loads(_CONTRACT_PATH.read_text(encoding="utf-8"))
        for t in data.get("tools", []):
            descriptions[t["name"]] = t.get("description", "")
    except (OSError, json.JSONDecodeError, KeyError):
        pass
    return [
        {"name": n, "description": descriptions.get(n, n),
         "inputSchema": {"type": "object", "additionalProperties": True}}
        for n in sorted(CONTRACT_TOOLS)
    ]


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    brain: Brain = None  # type: ignore[assignment]
    token: str = ""

    def log_message(self, *a):  # silence default stderr noise
        pass

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self) -> bool:
        if not self.token:
            return True  # no token configured (local/dev) — allow
        header = self.headers.get("Authorization", "")
        return header == f"Bearer {self.token}"

    def do_GET(self):
        # health probe for `ernest doctor` / load balancers
        if self.path.rstrip("/") in ("", "/health", "/healthz"):
            self._send(200, {"status": "ok", "service": "ernest-brain"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._authed():
            self._send(401, {"jsonrpc": "2.0", "id": None,
                             "error": {"code": -32001, "message": "unauthorized"}})
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            req = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"jsonrpc": "2.0", "id": None,
                             "error": {"code": -32700, "message": "parse error"}})
            return
        self._handle(req)

    def _result(self, rid, result):
        self._send(200, {"jsonrpc": "2.0", "id": rid, "result": result})

    def _error(self, rid, code, message):
        self._send(200, {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}})

    def _handle(self, req: dict):
        method = req.get("method", "")
        rid = req.get("id")
        if method == "initialize":
            self._result(rid, {
                "protocolVersion": req.get("params", {}).get("protocolVersion", "2025-06-18"),
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "ernest-brain", "version": "1.0.0"},
            })
        elif method in ("notifications/initialized", "notifications/cancelled"):
            self._send(202, {})  # notification, no result
        elif method == "ping":
            self._result(rid, {})
        elif method == "tools/list":
            self._result(rid, {"tools": _tool_specs()})
        elif method == "tools/call":
            params = req.get("params", {}) or {}
            name = params.get("name", "")
            args = params.get("arguments", {}) or {}
            out = self.brain.call(name, args)
            is_error = isinstance(out, dict) and "error" in out
            self._result(rid, {
                "content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}],
                "isError": bool(is_error),
            })
        else:
            self._error(rid, -32601, f"method not found: {method}")


_LOOPBACK = {"127.0.0.1", "::1", "localhost", ""}


def serve(host: str = "127.0.0.1", port: int = 8787) -> ThreadingHTTPServer:
    _Handler.brain = Brain()
    _Handler.token = os.environ.get("ERNEST_BRAIN_TOKEN", "").strip()
    # Fail closed: never expose an unauthenticated brain to the network. A token
    # is REQUIRED to bind a non-loopback host (loopback/dev may run open).
    if host not in _LOOPBACK and not _Handler.token:
        raise SystemExit(
            "Refusing to bind a non-loopback host without ERNEST_BRAIN_TOKEN — "
            "that would expose the brain unauthenticated. Set ERNEST_BRAIN_TOKEN "
            "(or bind 127.0.0.1 for local dev)."
        )
    httpd = ThreadingHTTPServer((host, port), _Handler)
    return httpd


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="brain.server")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args(argv)
    httpd = serve(args.host, args.port)
    where = f"{args.host}:{args.port}"
    auth = "bearer-protected" if _Handler.token else "OPEN (no ERNEST_BRAIN_TOKEN set)"
    print(f"ernest-brain MCP server on http://{where} ({auth})", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
