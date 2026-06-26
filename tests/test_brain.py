#!/usr/bin/env python3
"""Phase 5 — brain MCP server (the VPS sync surface).

Boots the real stdlib server on an ephemeral port and exercises the JSON-RPC
lifecycle, bearer auth, and the memory/watch/draft round-trips that let the VPS
and laptop share state. Draft-first by construction (no send tool exists).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILURES: list[str] = []
TOKEN = "test-bearer-123"


def check(label: str, condition: bool) -> None:
    print(f"  [{'ok  ' if condition else 'FAIL'}] {label}")
    if not condition:
        FAILURES.append(label)


def rpc(url: str, method: str, params=None, token: str = TOKEN, rid: int = 1):
    body = json.dumps({"jsonrpc": "2.0", "id": rid, "method": method,
                       "params": params or {}}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if token is not None:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, None


def tool_call(url: str, name: str, args=None):
    _, payload = rpc(url, "tools/call", {"name": name, "arguments": args or {}})
    text = payload["result"]["content"][0]["text"]
    return json.loads(text), payload["result"].get("isError", False)


def test_brain_server_lifecycle() -> None:
    sandbox = Path(tempfile.mkdtemp(prefix="ernest_brain_"))
    os.environ["ERNEST_PROFILE_DIR"] = str(ROOT)        # gate/config resolve against repo
    os.environ["ERNEST_LOCAL_VAULT"] = str(sandbox / "vault")
    os.environ["ERNEST_BRAIN_TOKEN"] = TOKEN
    # isolate memory writes from the repo's real memory dir
    mem = sandbox / "memory"
    mem.mkdir(parents=True)
    (mem / "company-core.md").write_text("# Company\n\nNorthwind is the company.\n", encoding="utf-8")

    from brain import server
    from brain.brain_core import Brain
    from ernest import config
    # Point the brain at the sandbox memory by overriding config via env-built Config.
    cfg = config.load()
    brain = Brain(cfg)
    brain.cfg = cfg.__class__(**{**cfg.__dict__, "memory_dir": mem})
    brain.mem_log = mem / "brain-memory.jsonl"

    httpd = server.serve("127.0.0.1", 0)
    server._Handler.brain = brain
    server._Handler.token = TOKEN
    port = httpd.server_address[1]
    url = f"http://127.0.0.1:{port}"
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        # initialize / tools/list
        status, init = rpc(url, "initialize", {"protocolVersion": "2025-06-18"})
        check("initialize 200", status == 200 and init["result"]["serverInfo"]["name"] == "ernest-brain")
        _, tl = rpc(url, "tools/list")
        names = {t["name"] for t in tl["result"]["tools"]}
        check("tools/list has contract tools", {"health", "search_memory", "write_memory",
              "write_watch_card", "create_mail_draft"} <= names)
        check("no send/post tool exists (draft-first by construction)",
              not any("send" in n or "post" in n or "publish" in n for n in names))

        # auth: wrong + missing bearer -> 401
        bad, _ = rpc(url, "tools/list", token="wrong")
        check("wrong bearer -> 401", bad == 401)
        none, _ = rpc(url, "tools/list", token=None)
        check("missing bearer -> 401", none == 401)

        # health
        health, err = tool_call(url, "health")
        check("health ok", not err and health["status"] == "ok" and health["draft_first_gate"] == "enabled")

        # memory write -> search round trip
        w, _ = tool_call(url, "write_memory", {"text": "CEO prefers PDF digests on Fridays", "scope": "preferences"})
        check("write_memory ok", w.get("ok") is True)
        s, _ = tool_call(url, "search_memory", {"query": "pdf digests"})
        check("search_memory finds written note", s["count"] >= 1 and any("PDF" in r["text"] for r in s["results"]))
        s2, _ = tool_call(url, "search_memory", {"query": "Northwind"})
        check("search_memory reads markdown memory", any("Northwind" in r["text"] for r in s2["results"]))

        # watch card write + dedupe + list
        c1, _ = tool_call(url, "write_watch_card", {"concern_id": "dropped-followup",
                          "source_ref": "thread/abc", "due_date": "2026-06-30", "body": "Re-ping Acme"})
        c2, _ = tool_call(url, "write_watch_card", {"concern_id": "dropped-followup",
                          "source_ref": "thread/abc", "due_date": "2026-06-30", "body": "Re-ping Acme (again)"})
        check("watch card created", c1.get("ok") is True)
        check("same slip dedupes to one card id", c1["id"] == c2["id"])
        lst, _ = tool_call(url, "list_watch_cards", {"concern": "dropped-followup"})
        check("list_watch_cards returns the card once", lst["count"] == 1)

        # draft creation: produces a draft, never sends
        d, _ = tool_call(url, "create_mail_draft", {"to": "a@b.com", "subject": "Hi", "body": "Draft body"})
        check("create_mail_draft -> draft state", d.get("state") == "draft" and d.get("ok") is True)

        # connector read with nothing configured -> honest needs_config, never fakes
        m, _ = tool_call(url, "search_mail", {"query": "x"})
        check("unconfigured connector says needs_config", m.get("status") == "needs_config")

        # unknown tool refused
        u, err = tool_call(url, "definitely_not_a_tool")
        check("unknown tool refused", err and "unknown tool" in u.get("error", ""))
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    test_brain_server_lifecycle()
    if FAILURES:
        print(f"FAILED {len(FAILURES)} checks:")
        for failure in FAILURES:
            print(f"  - {failure}")
        raise SystemExit(1)
    print("PASS - brain server: JSON-RPC, auth, memory/watch/draft sync, draft-first")
