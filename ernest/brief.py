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


def compose(cfg: Config) -> Tuple[str, str]:
    """Return (markdown_for_file, short_stdout_summary)."""
    items = detect(cfg)
    threads = load_threads(cfg)
    contacts = load_contacts(cfg)

    needs_you: List[WatchItem] = sorted(
        items, key=lambda i: i.thread.days_waiting(cfg.today), reverse=True
    )

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
            t = item.thread
            md_lines.append(
                f"- [{item.concern_id}] {t.contact or 'Unknown'} ({t.company or 'Unknown'}) "
                f"- waiting {t.days_waiting(cfg.today)}d - {item.suggested_action}"
            )
    else:
        md_lines.append("- Nothing waiting on you. Inbox is clean.")
    md_lines += [
        "",
        "## Next step",
        "- Run `ernest draft --concern <id>` to prepare draft-only replies for review.",
        "",
    ]

    summary = (
        f"Morning brief {cfg.today.isoformat()}: {len(needs_you)} follow-up(s) need you, "
        f"{len(threads)} open thread(s)."
    )
    return "\n".join(md_lines), summary


def run(cfg: Config) -> Tuple[Path, str]:
    ensure_dirs(cfg)
    markdown, summary = compose(cfg)
    path = cfg.daily_dir / f"brief--{cfg.today.isoformat()}.md"
    path.write_text(markdown, encoding="utf-8")
    return path, summary
