"""Draft-only outreach generation.

This is the only place the engine produces outbound language, and it never
sends. Every draft is written to the vault drafts folder, labeled
`STATUS: DRAFT`, and carries its `source`. Sending is a separate, human-approved
step performed through a connector at the Claude layer (and blocked by the gate
until approved).
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .concerns import load as load_concerns
from .config import Config, ensure_dirs
from .sources import Thread
from .watch import WatchItem, detect


def _first_name(contact: str) -> str:
    return (contact or "there").split()[0] if contact else "there"


def _draft_body(item: WatchItem) -> str:
    t = item.thread
    return (
        f"Hi {_first_name(t.contact)},\n\n"
        f"Following up on your note from {t.last_inbound} - thanks for your patience. "
        f"{t.summary or 'Picking this back up on our side.'}\n\n"
        f"Happy to move this forward. Does a short call this week work, or shall I send details over email?\n\n"
        f"Best,\nSam"
    )


def _draft_block(item: WatchItem) -> str:
    t = item.thread
    return "\n".join([
        f"## To: {t.contact or 'Unknown'} ({t.company or 'Unknown'})",
        "STATUS: DRAFT - not sent. Review, then approve a send through a connector.",
        f"source: {t.source}",
        f"context: inbound {t.last_inbound} - {item.reason}",
        f"subject: Re: {t.subject or 'Following up'}",
        "",
        _draft_body(item),
        "",
        "---",
        "",
    ])


def collect(cfg: Config, concern_id: Optional[str], contact: Optional[str]) -> List[WatchItem]:
    items = detect(cfg)
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
    blocks = [_draft_block(item) for item in items]
    path = cfg.drafts_dir / f"{label}--{cfg.today.isoformat()}.md"
    path.write_text("\n".join(header) + "\n" + "\n".join(blocks), encoding="utf-8")
    return path
