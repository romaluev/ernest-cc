"""Draft-only outreach generation.

This is the only place the engine produces outbound language, and it never
sends. Every draft is written to the vault drafts folder, labeled
`STATUS: DRAFT`, and carries its `source`. Sending is a separate, human-approved
step performed through a connector at the Claude layer (and blocked by the gate
until approved).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from .concerns import load as load_concerns
from .config import Config, ensure_dirs
from .thread_reader import load_one as load_conversation
from .watch import WatchItem, detect


def _first_name(contact: str) -> str:
    return (contact or "there").split()[0] if contact else "there"


def _ceo_name(cfg: Config) -> str:
    """The CEO's name from memory, for the signature. Never fabricate one."""
    p = cfg.memory_dir / "ceo-persona.md"
    if p.is_file():
        m = re.search(r"^-\s*Name:\s*(.+)$", p.read_text(encoding="utf-8"), re.M)
        if m:
            name = m.group(1).strip()
            if name and "onboarding" not in name.lower() and name != "(set during onboarding)":
                return name.split()[0]
    return ""


def _clean_subject(subject: str) -> str:
    s = (subject or "Following up").strip()
    s = re.sub(r"^(re:\s*)+", "", s, flags=re.I).strip()  # avoid "Re: Re:"
    return s or "Following up"


def _draft_body(cfg: Config, item: WatchItem) -> str:
    # IMPORTANT: never echo the recipient's inbound text or an internal summary
    # into the reply — a draft may be forwarded. Reference our own topic only.
    t = item.thread
    topic = _clean_subject(t.subject) if t.subject else "this"
    sig_name = _ceo_name(cfg)
    signoff = f"Best,\n{sig_name}" if sig_name else "Best,\n[your name]"
    return (
        f"Hi {_first_name(t.contact)},\n\n"
        f"Following up on {topic} — thanks for your patience, and sorry for the delay on my side. "
        f"I'd love to move this forward.\n\n"
        f"Would a short call this week work, or would you prefer I send the details by email?\n\n"
        f"{signoff}"
    )


def _draft_block(cfg: Config, item: WatchItem) -> str:
    t = item.thread
    conv = load_conversation(cfg, t.id)
    thread_ref = f"thread: {t.id} ({conv.message_count} messages read)" if conv and conv.message_count else f"thread: {t.id}"
    return "\n".join([
        f"## To: {t.contact or 'Unknown'} ({t.company or 'Unknown'})",
        "STATUS: DRAFT - not sent. Review, then approve a send through a connector.",
        f"source: {t.source}",
        thread_ref,
        f"context: inbound {t.last_inbound} - {item.reason}",
        f"subject: Re: {_clean_subject(t.subject)}",
        "",
        _draft_body(cfg, item),
        "",
        "---",
        "",
    ])


def collect(cfg: Config, concern_id: Optional[str], contact: Optional[str]) -> List[WatchItem]:
    # Only thread-backed items are draftable. Assign/sync items are remind-only.
    items = [i for i in detect(cfg) if i.thread is not None]
    if concern_id:
        items = [i for i in items if i.concern_id == concern_id]
    if contact:
        needle = contact.lower()
        items = [i for i in items if needle in (i.thread.contact or "").lower()
                 or needle in (i.thread.company or "").lower()]
    return items


def run(cfg: Config, concern_id: Optional[str] = None,
        contact: Optional[str] = None) -> Optional[Path]:
    ensure_dirs(cfg)
    items = collect(cfg, concern_id, contact)
    if not items:
        return None
    label = concern_id or (contact.replace(" ", "-").lower() if contact else "drafts")
    header = [
        f"# Drafts: {label} ({cfg.today.isoformat()})",
        "",
        "STATUS: DRAFT - none of these have been sent.",
        "source: local-export",
        f"drafts: {len(items)}",
        "",
    ]
    blocks = [_draft_block(cfg, item) for item in items]
    path = cfg.drafts_dir / f"{label}--{cfg.today.isoformat()}.md"
    path.write_text("\n".join(header) + "\n" + "\n".join(blocks), encoding="utf-8")
    return path
