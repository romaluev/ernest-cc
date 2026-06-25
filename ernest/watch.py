"""Ambient watch: turn standing concerns + sources into reminder cards.

Detection is deterministic and remind-only. Cards never contain drafts; they
state what slipped and the suggested next action, and point at `ernest draft`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List

from .concerns import Concern, load as load_concerns
from .config import Config, ensure_dirs
from .sources import Thread, load_threads

_TARGET_INTENTS = {"partnership", "sales", "investor", "press", "hire", "inbound"}


def _days_param(value: str, default: int) -> int:
    match = re.search(r"(\d+)", value or "")
    return int(match.group(1)) if match else default


@dataclass
class WatchItem:
    concern_id: str
    thread: Thread
    reason: str
    suggested_action: str


def _match(concern: Concern, threads: List[Thread], today: date) -> List[WatchItem]:
    items: List[WatchItem] = []
    if concern.playbook == "account-followup-recovery":
        staleness = _days_param(concern.params.get("staleness", ""), 7)
        for t in threads:
            if t.owed and t.days_waiting(today) >= staleness:
                items.append(WatchItem(
                    concern.id, t,
                    f"Inbound {t.days_waiting(today)}d ago with no reply (threshold {staleness}d).",
                    "Reply to keep the thread alive.",
                ))
    elif concern.playbook == "inbox-prospect-followup":
        wanted = concern.params.get("intent", "").lower()
        window = _days_param(concern.params.get("window", ""), 90)
        for t in threads:
            intent_ok = (not wanted) or (t.intent == wanted) or (t.intent in _TARGET_INTENTS)
            if t.owed and intent_ok and t.days_waiting(today) <= window:
                items.append(WatchItem(
                    concern.id, t,
                    f"Inbound {t.intent or 'prospect'} lead waiting {t.days_waiting(today)}d.",
                    "Qualify and send a first follow-up.",
                ))
    return items


def detect(cfg: Config) -> List[WatchItem]:
    threads = load_threads(cfg)
    items: List[WatchItem] = []
    for concern in load_concerns(cfg):
        if concern.enabled:
            items.extend(_match(concern, threads, cfg.today))
    return items


def _card(cfg: Config, concern_id: str, items: List[WatchItem]) -> str:
    lines = [
        f"# Watch: {concern_id} ({cfg.today.isoformat()})",
        "",
        "type: reminder-card",
        "source: local-export",
        f"items: {len(items)}",
        "",
        "Say \"draft these\" to turn this card into draft-only outreach.",
        "",
    ]
    for n, item in enumerate(items, 1):
        t = item.thread
        lines += [
            f"## {n}. {t.contact or 'Unknown'} - {t.company or 'Unknown'}",
            f"- waiting: {t.days_waiting(cfg.today)}d (last inbound {t.last_inbound})",
            f"- why: {item.reason}",
            f"- suggested: {item.suggested_action}",
            f"- context: {t.summary or t.status or t.subject}",
            "",
        ]
    return "\n".join(lines)


def run(cfg: Config) -> List[Path]:
    ensure_dirs(cfg)
    items = detect(cfg)
    by_concern: dict[str, List[WatchItem]] = {}
    for item in items:
        by_concern.setdefault(item.concern_id, []).append(item)
    written: List[Path] = []
    for concern_id, group in by_concern.items():
        path = cfg.watch_dir / f"{concern_id}--{cfg.today.isoformat()}.md"
        path.write_text(_card(cfg, concern_id, group), encoding="utf-8")
        written.append(path)
    return written
