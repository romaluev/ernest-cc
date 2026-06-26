"""Full conversation threads: email, Slack, and other messaging exports.

Watch/draft need message bodies, not just metadata snippets. This module loads
complete threads from local exports and caches them in the vault. Live MCP reads
are orchestrated at the Claude layer via the `read-thread` skill.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from .config import Config

_MSG_HEADING = re.compile(
    r"^###\s+(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?\s*\|\s*(.+?)\s*\((inbound|outbound)\)\s*$",
    re.IGNORECASE,
)


@dataclass
class Message:
    at: date
    author: str
    direction: str  # inbound | outbound
    body: str
    time: str = ""

    @property
    def is_inbound(self) -> bool:
        return self.direction.lower() == "inbound"


@dataclass
class Conversation:
    thread_id: str
    channel: str  # email | slack | teams | other
    contact: str = ""
    company: str = ""
    subject: str = ""
    status: str = ""
    source: str = "local-export"
    origin: str = ""
    messages: List[Message] = field(default_factory=list)

    @property
    def message_count(self) -> int:
        return len(self.messages)

    def last_inbound(self) -> Optional[Message]:
        for msg in reversed(self.messages):
            if msg.is_inbound:
                return msg
        return None

    def last_outbound(self) -> Optional[Message]:
        for msg in reversed(self.messages):
            if not msg.is_inbound:
                return msg
        return None

    def excerpt(self, limit: int = 280) -> str:
        last = self.last_inbound() or (self.messages[-1] if self.messages else None)
        if not last:
            return ""
        text = " ".join(last.body.split())
        return text[:limit] + ("…" if len(text) > limit else "")


def _parse_date(value: str) -> Optional[date]:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_header(lines: List[str]) -> tuple[dict[str, str], int]:
    header: dict[str, str] = {}
    body_start = 0
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped.startswith("#"):
            continue
        if stripped == "---":
            body_start = idx + 1
            break
        if not stripped:
            if header:
                body_start = idx + 1
                break
            continue
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            header[key.strip().lower()] = val.strip()
        else:
            body_start = idx
            break
    return header, body_start


def _parse_message_blocks(lines: List[str], start: int) -> List[Message]:
    messages: List[Message] = []
    idx = start
    while idx < len(lines):
        match = _MSG_HEADING.match(lines[idx].strip())
        if not match:
            idx += 1
            continue
        at = _parse_date(match.group(1))
        if at is None:
            idx += 1
            continue
        time_part = match.group(2) or ""
        author = match.group(3).strip()
        direction = match.group(4).lower()
        idx += 1
        body_lines: List[str] = []
        while idx < len(lines):
            if _MSG_HEADING.match(lines[idx].strip()):
                break
            body_lines.append(lines[idx])
            idx += 1
        body = "\n".join(body_lines).strip()
        if body:
            messages.append(Message(at=at, author=author, direction=direction,
                                    body=body, time=time_part))
    return messages


def _legacy_body_summary(lines: List[str], start: int) -> List[Message]:
    """Threads exported before message blocks: treat prose after header as one blob."""
    text = "\n".join(lines[start:]).strip()
    if not text or _MSG_HEADING.search(text):
        return []
    return [Message(at=date.today(), author="", direction="inbound", body=text)]


def parse_markdown(path: Path) -> Optional[Conversation]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    header, body_start = _parse_header(lines)
    if not header:
        return None
    messages = _parse_message_blocks(lines, body_start)
    if not messages:
        messages = _legacy_body_summary(lines, body_start)
    channel = header.get("channel", "email").lower()
    if "slack" in path.parts and channel == "email":
        channel = "slack"
    return Conversation(
        thread_id=header.get("thread_id", path.stem),
        channel=channel,
        contact=header.get("contact", ""),
        company=header.get("company", ""),
        subject=header.get("subject", ""),
        status=header.get("status", ""),
        source=header.get("source", "local-export"),
        origin=str(path),
        messages=messages,
    )


def parse_json(path: Path) -> List[Conversation]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    records = raw if isinstance(raw, list) else [raw]
    out: List[Conversation] = []
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            continue
        messages: List[Message] = []
        for j, msg in enumerate(rec.get("messages") or []):
            if not isinstance(msg, dict):
                continue
            at = _parse_date(str(msg.get("at", "")))
            if at is None:
                continue
            messages.append(Message(
                at=at,
                author=str(msg.get("from", msg.get("author", ""))),
                direction=str(msg.get("direction", "inbound")).lower(),
                body=str(msg.get("body", "")).strip(),
                time=str(msg.get("time", "")),
            ))
        out.append(Conversation(
            thread_id=str(rec.get("thread_id") or rec.get("id") or f"{path.stem}-{i}"),
            channel=str(rec.get("channel", "email")).lower(),
            contact=str(rec.get("contact", "")),
            company=str(rec.get("company", "")),
            subject=str(rec.get("subject", "")),
            status=str(rec.get("status", "")),
            source=str(rec.get("source", "local-export")),
            origin=str(path),
            messages=messages,
        ))
    return out


def _iter_export_paths(cfg: Config) -> Iterator[Path]:
    for sub in ("mail", "slack/threads", "messages"):
        base = cfg.data_dir / sub
        if not base.is_dir():
            continue
        for path in sorted(base.iterdir()):
            if path.suffix.lower() in (".md", ".json"):
                yield path


def load_all(cfg: Config) -> Dict[str, Conversation]:
    """Index all exported conversations by thread_id."""
    index: Dict[str, Conversation] = {}
    for path in _iter_export_paths(cfg):
        try:
            if path.suffix.lower() == ".md":
                conv = parse_markdown(path)
                if conv:
                    index[conv.thread_id] = conv
            elif path.suffix.lower() == ".json":
                for conv in parse_json(path):
                    index[conv.thread_id] = conv
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return index


def load_one(cfg: Config, thread_id: str) -> Optional[Conversation]:
    needle = thread_id.strip().lower()
    for tid, conv in load_all(cfg).items():
        if tid.lower() == needle:
            return conv
        if conv.origin and needle in Path(conv.origin).stem.lower():
            return conv
    return None


def render(conversation: Conversation) -> str:
    lines = [
        f"# Thread: {conversation.subject or conversation.thread_id}",
        "",
        f"thread_id: {conversation.thread_id}",
        f"channel: {conversation.channel}",
        f"source: {conversation.source}",
    ]
    if conversation.contact:
        lines.append(f"contact: {conversation.contact}")
    if conversation.company:
        lines.append(f"company: {conversation.company}")
    if conversation.status:
        lines.append(f"status: {conversation.status}")
    lines += ["", f"messages: {conversation.message_count}", "", "---", ""]
    for msg in conversation.messages:
        time_suffix = f" {msg.time}" if msg.time else ""
        lines.append(f"### {msg.at.isoformat()}{time_suffix} | {msg.author} ({msg.direction})")
        lines.append("")
        lines.append(msg.body)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def threads_dir(cfg: Config) -> Path:
    return cfg.vault_dir / "Ernest" / "00-Threads"


def cache_path(cfg: Config, thread_id: str) -> Path:
    safe = re.sub(r"[^\w.-]+", "-", thread_id).strip("-") or "thread"
    return threads_dir(cfg) / f"{safe}.md"


def conversation_to_thread(conv: Conversation) -> "Thread":
    from .sources import Thread

    inbound = [m.at for m in conv.messages if m.is_inbound]
    outbound = [m.at for m in conv.messages if not m.is_inbound]
    category = conv.channel if conv.channel != "email" else ""
    return Thread(
        id=conv.thread_id,
        contact=conv.contact,
        company=conv.company,
        last_inbound=max(inbound) if inbound else None,
        last_outbound=max(outbound) if outbound else None,
        status=conv.status,
        subject=conv.subject,
        summary=conv.excerpt(280),
        category=category,
        source=conv.source,
        origin=conv.origin,
    )


def write_cache(cfg: Config, conversation: Conversation) -> Path:
    path = cache_path(cfg, conversation.thread_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(conversation), encoding="utf-8")
    return path
