"""Daily brief: the one screen the CEO reads each morning.

Composed from the day's watch items plus source counts. Deterministic, so the
same inputs always yield the same brief.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from .config import Config, ensure_dirs
from .sources import load_contacts, load_threads
from .watch import WatchItem, detect


def _sort_key(item: WatchItem) -> int:
    return item.waiting_days if item.waiting_days is not None else -1


def compose(cfg: Config) -> Tuple[str, str]:
    """Return (markdown_for_file, short_stdout_summary)."""
    items = detect(cfg)
    threads = load_threads(cfg)
    contacts = load_contacts(cfg)

    needs_you: List[WatchItem] = sorted(items, key=_sort_key, reverse=True)
    followups = sum(1 for i in items if i.waiting_days is not None)

    md_lines = [
        f"# Morning brief - {cfg.today.isoformat()}",
        "",
        "source: local-export",
        f"open threads: {len(threads)} | tracked contacts: {len(contacts)} | needs you: {len(needs_you)}",
        "",
        "## Needs you today",
    ]
    if needs_you:
        for item in needs_you:
            wait = f"waiting {item.waiting_days}d - " if item.waiting_days is not None else ""
            md_lines.append(
                f"- [{item.concern_id}] {item.title} - {wait}{item.suggested_action}"
            )
    else:
        md_lines.append("- Nothing waiting on you. Inbox is clean.")
    md_lines += [
        "",
        "## Next step",
        "- Run `ernest draft --concern <id>` to prepare draft-only replies for review.",
        "- Watch cards in `00-Watch/` list assignments and syncs (remind-only).",
        "",
    ]

    summary = (
        f"Morning brief {cfg.today.isoformat()}: {followups} follow-up(s) need you, "
        f"{len(needs_you)} open loop(s) across {len(threads)} thread(s)."
    )
    return "\n".join(md_lines), summary


def run(cfg: Config) -> Tuple[Path, str]:
    ensure_dirs(cfg)
    markdown, summary = compose(cfg)
    path = cfg.daily_dir / f"brief--{cfg.today.isoformat()}.md"
    path.write_text(markdown, encoding="utf-8")
    return path, summary
