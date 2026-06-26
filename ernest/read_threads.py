"""Load and cache full conversation threads for watch/draft."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .config import Config, ensure_dirs
from .thread_reader import Conversation, cache_path, load_all, load_one, write_cache
from .watch import WatchItem, detect


def collect_thread_ids(cfg: Config, *, concern_id: Optional[str] = None,
                       thread_id: Optional[str] = None, owed_only: bool = False) -> List[str]:
    if thread_id:
        return [thread_id]
    ids: List[str] = []
    seen: set[str] = set()
    if owed_only:
        for item in detect(cfg):
            if concern_id and item.concern_id != concern_id:
                continue
            if item.thread is None:
                continue
            tid = item.thread.id
            if tid not in seen:
                seen.add(tid)
                ids.append(tid)
        return ids
    for tid in load_all(cfg):
        if tid not in seen:
            seen.add(tid)
            ids.append(tid)
    return ids


def run(cfg: Config, *, thread_id: Optional[str] = None, concern_id: Optional[str] = None,
        owed_only: bool = False) -> List[Path]:
    ensure_dirs(cfg)
    written: List[Path] = []
    missing: List[str] = []
    for tid in collect_thread_ids(cfg, concern_id=concern_id, thread_id=thread_id,
                                   owed_only=owed_only):
        conv = load_one(cfg, tid)
        if conv is None or conv.message_count == 0:
            missing.append(tid)
            continue
        written.append(write_cache(cfg, conv))
    if missing and not written:
        raise ValueError(
            f"No readable thread bodies for: {', '.join(missing)}. "
            "Export full threads to data/mail/ or data/slack/threads/ — see data/README.md."
        )
    return written


def manifest_for_claude(cfg: Config, paths: List[Path]) -> str:
    lines = [
        f"# Thread read manifest ({cfg.today.isoformat()})",
        "",
        f"cached: {len(paths)}",
        "",
    ]
    for path in paths:
        lines.append(f"- {path}")
    if not paths:
        lines.append("_No threads cached. Connect mail/Slack MCP and run /ernest-read._")
    lines.append("")
    lines.append("Live MCP: use read-thread skill to fetch bodies not in exports.")
    return "\n".join(lines)
