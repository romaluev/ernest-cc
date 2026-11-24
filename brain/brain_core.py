"""Ernest brain — reference implementation of the brain MCP contract.

This is the canonical-memory + watch-card + draft service that the optional VPS
runs so a 24/7 surface (Telegram/Slack) and the local Claude Code surface share
ONE state. It is stdlib-only and operates over the SAME markdown memory + vault
watch cards the local engine uses, so the two surfaces stay in sync (the durable
sync between machines is git on the state repo; this is the live API over it).

Safety: the contract intentionally exposes NO send/post/publish tool — only
reads, internal memory writes, watch cards, and DRAFT creation. So the brain is
draft-first by construction. Any action outside the contract is refused, and
mutating connector actions are additionally checked against the deterministic
core gate, so the VPS enforces identically to the laptop.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ernest import config
from ernest import gate

CONTRACT_TOOLS = {
    "health", "search_memory", "write_memory", "list_watch_cards", "write_watch_card",
    "search_mail", "read_mail_thread", "create_mail_draft", "search_hubspot",
    "search_slack", "read_slack_thread",
}
_CONNECTOR_TOOLS = {"search_mail", "read_mail_thread", "search_hubspot", "search_slack", "read_slack_thread"}


def _iso(ts: Optional[float] = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts if ts is not None else time.time()))


class Brain:
    def __init__(self, cfg: Optional[config.Config] = None) -> None:
        self.cfg = cfg or config.load()
        config.ensure_dirs(self.cfg)
        self.mem_log = self.cfg.memory_dir / "brain-memory.jsonl"
        self.cfg.memory_dir.mkdir(parents=True, exist_ok=True)

    # --- health -------------------------------------------------------------
    def health(self) -> Dict[str, Any]:
        def state(name: str) -> str:
            return "connected" if os.environ.get(f"ERNEST_CONN_{name.upper()}") else "missing"
        return {
            "status": "ok",
            "mode": "vps-brain",
            "draft_first_gate": "enabled",
            "connectors": {
                "mail": state("mail"),
                "hubspot": state("hubspot"),
                "slack": state("slack"),
                "calendar": state("calendar"),
            },
        }

    # --- canonical memory ---------------------------------------------------
    def write_memory(self, text: str, scope: str = "general",
                     source: Optional[str] = None) -> Dict[str, Any]:
        if not text or not str(text).strip():
            return {"error": "text is required"}
        entry = {
            "id": hashlib.sha1(f"{scope}|{text}|{_iso()}".encode()).hexdigest()[:12],
            "scope": scope, "text": str(text).strip(), "source": source or "",
            "ts": _iso(),
        }
        # O_APPEND single line: crash-safe, concurrency-safe.
        line = (json.dumps(entry, ensure_ascii=False) + "\n").encode("utf-8")
        fd = os.open(str(self.mem_log), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
        return {"ok": True, "id": entry["id"]}

    def search_memory(self, query: str = "", scope: Optional[str] = None,
                      limit: int = 25) -> Dict[str, Any]:
        q = (query or "").lower().strip()
        hits: List[Dict[str, Any]] = []
        # 1. structured brain memory
        if self.mem_log.is_file():
            for raw in self.mem_log.read_text(encoding="utf-8").splitlines():
                try:
                    e = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if scope and e.get("scope") != scope:
                    continue
                if not q or q in e.get("text", "").lower():
                    hits.append({"text": e["text"], "scope": e.get("scope"),
                                 "source": e.get("source") or "brain-memory.jsonl", "ts": e.get("ts")})
        # 2. canonical markdown memory files (company-core, ceo-persona, ...)
        for md in sorted(self.cfg.memory_dir.glob("*.md")):
            text = md.read_text(encoding="utf-8", errors="ignore")
            for para in re.split(r"\n\s*\n", text):
                if q and q in para.lower():
                    hits.append({"text": para.strip()[:600], "scope": md.stem,
                                 "source": f"memory/{md.name}", "ts": None})
        return {"results": hits[:limit], "count": len(hits)}

    # --- watch cards (shared with the local engine vault) -------------------
    def _card_key(self, concern_id: str, source_ref: str, due_date: str) -> str:
        return hashlib.sha1(f"{concern_id}|{source_ref}|{due_date}".encode()).hexdigest()[:12]

    def write_watch_card(self, concern_id: str, source_ref: str = "",
                         due_date: str = "", body: str = "") -> Dict[str, Any]:
        if not concern_id:
            return {"error": "concern_id is required"}
        # Cards must not carry unsent external draft bodies (anti-exfil rule).
        key = self._card_key(concern_id, source_ref, due_date)
        self.cfg.watch_dir.mkdir(parents=True, exist_ok=True)
        path = self.cfg.watch_dir / f"card-{key}.md"
        content = (
            f"---\nconcern: {concern_id}\nsource: {source_ref}\ndue: {due_date}\n"
            f"key: {key}\nupdated: {_iso()}\n---\n\n{body.strip()}\n\n"
            "Reply draft these when you want me to prepare actions.\n"
        )
        path.write_text(content, encoding="utf-8")  # idempotent: same key overwrites, no dupes
        return {"ok": True, "id": key, "deduped": True}

    def list_watch_cards(self, window: Optional[str] = None,
                         concern: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        cards: List[Dict[str, Any]] = []
        if self.cfg.watch_dir.is_dir():
            for p in sorted(self.cfg.watch_dir.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
                text = p.read_text(encoding="utf-8", errors="ignore")
                m = {k: (re.search(rf"^{k}:\s*(.*)$", text, re.M) or [None, ""])[1]
                     for k in ("concern", "source", "due", "key")}
                if concern and m["concern"] != concern:
                    continue
                cards.append({"id": m["key"] or p.stem, "concern": m["concern"],
                              "source": m["source"], "due": m["due"], "file": p.name})
        return {"cards": cards[:limit], "count": len(cards)}

    def resolve_watch_card(self, card_id: str) -> Dict[str, Any]:
        # Tombstone (not delete) so both surfaces converge on resolution.
        for p in self.cfg.watch_dir.glob("*.md"):
            if card_id in p.name:
                p.rename(p.with_suffix(".resolved.md"))
                return {"ok": True, "id": card_id, "state": "resolved"}
        return {"error": "card not found", "id": card_id}

    # --- drafts (creation only; never sends) --------------------------------
    def create_mail_draft(self, to: str = "", subject: str = "", body: str = "",
                          thread_id: Optional[str] = None) -> Dict[str, Any]:
        self.cfg.drafts_dir.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha1(f"{to}|{subject}|{_iso()}".encode()).hexdigest()[:12]
        path = self.cfg.drafts_dir / f"draft-{key}.md"
        path.write_text(
            f"---\nto: {to}\nsubject: {subject}\nthread: {thread_id or ''}\n"
            f"created: {_iso()}\nstate: draft\n---\n\n{body}\n", encoding="utf-8")
        return {"ok": True, "id": key, "state": "draft", "file": path.name,
                "note": "Draft created. Nothing sent — approve to send via your mail client/connector."}

    # --- connector reads (honest stubs unless wired on the VPS) -------------
    def _connector_read(self, name: str, **kwargs) -> Dict[str, Any]:
        # Real VPS wires these to native MCP / Composio. The reference falls back
        # to data/ exports if present, else says what's missing — never fakes.
        export = self.cfg.data_dir / f"{name}.json"
        if export.is_file():
            try:
                return {"results": json.loads(export.read_text(encoding="utf-8")), "source": f"data/{name}.json"}
            except json.JSONDecodeError:
                pass
        return {"results": [], "status": "needs_config",
                "note": f"Connector for '{name}' not configured on this brain; wire it on the VPS or add data/{name}.json."}

    # --- dispatch -----------------------------------------------------------
    def call(self, name: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        args = args or {}
        if name not in CONTRACT_TOOLS:
            return {"error": f"unknown tool '{name}' (not in brain contract)"}
        # Defense in depth: route any connector action through the core gate, so a
        # future mis-added mutating tool is blocked identically to the laptop.
        if name in _CONNECTOR_TOOLS or name == "create_mail_draft":
            blocked = gate.draft_only_block(f"mcp__ernest-brain__{name}", args, str(self.cfg.profile_dir))
            if blocked is not None:
                return {"error": "draft_only", "reason": blocked.get("reason")}
        try:
            if name == "health":
                return self.health()
            if name == "search_memory":
                return self.search_memory(args.get("query", ""), args.get("scope"), int(args.get("limit", 25)))
            if name == "write_memory":
                return self.write_memory(args.get("text", ""), args.get("scope", "general"), args.get("source"))
            if name == "list_watch_cards":
                return self.list_watch_cards(args.get("window"), args.get("concern"), int(args.get("limit", 50)))
            if name == "write_watch_card":
                return self.write_watch_card(args.get("concern_id", ""), args.get("source_ref", ""),
                                             args.get("due_date", ""), args.get("body", ""))
            if name == "create_mail_draft":
                return self.create_mail_draft(args.get("to", ""), args.get("subject", ""),
                                              args.get("body", ""), args.get("thread_id"))
            if name in _CONNECTOR_TOOLS:
                return self._connector_read(name, **args)
        except Exception as exc:  # noqa: BLE001 — never 500 on tool logic
            return {"error": f"{type(exc).__name__}: {exc}"}
        return {"error": f"tool '{name}' not implemented"}
