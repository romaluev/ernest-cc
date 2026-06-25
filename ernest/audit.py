"""Deep mail audit: chunked sweep for owed replies over a long window.

Daily `ernest watch` uses short staleness defaults (7d) and is cheap. A CEO
"full year audit" needs an explicit window, date-bucketed search, and a rule to
finish every bucket before summarizing — otherwise live MCP runs stop after the
first recent page of results.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

from .concerns import Concern
from .config import Config, ensure_dirs
from .sources import load_threads
from .watch import WatchItem, _account_followup


def _days_param(value: str, default: int) -> int:
    match = re.search(r"(\d+)", value or "")
    return int(match.group(1)) if match else default


@dataclass
class AuditChunk:
    index: int
    start: date
    end: date

    @property
    def label(self) -> str:
        return f"{self.start.isoformat()}..{self.end.isoformat()}"


def build_chunks(today: date, window_days: int, chunk_days: int = 30) -> List[AuditChunk]:
    """Split `window_days` into backward buckets ending at `today`."""
    if window_days <= 0:
        return []
    chunk_days = max(1, chunk_days)
    chunks: List[AuditChunk] = []
    cursor_end = today
    remaining = window_days
    idx = 1
    while remaining > 0:
        span = min(chunk_days, remaining)
        start = cursor_end - timedelta(days=span - 1)
        chunks.append(AuditChunk(index=idx, start=start, end=cursor_end))
        cursor_end = start - timedelta(days=1)
        remaining -= span
        idx += 1
    return chunks


def _manifest(cfg: Config, window_days: int, staleness_days: int, chunk_days: int,
              chunks: List[AuditChunk]) -> str:
    lines = [
        f"# Mail audit manifest ({cfg.today.isoformat()})",
        "",
        "type: audit-manifest",
        f"window_days: {window_days}",
        f"staleness_days: {staleness_days}",
        f"chunk_days: {chunk_days}",
        f"chunks_total: {len(chunks)}",
        "",
        "## Rules for live mail (MCP)",
        "",
        "1. Process **every chunk below** before writing the final summary.",
        "2. Do **not** stop after the first page or the most recent cluster.",
        "3. Do **not** ask the CEO to continue mid-audit unless a connector is blocked.",
        "4. For each chunk: search Inbox + Sent, find threads where they wrote last",
        "   and you never replied; verify in Sent; dedupe by thread id.",
        "5. Exclude noise: newsletters, job-seeker intros, cold vendor outreach unless",
        "   the CEO asked to include them.",
        "6. Rank by revenue, investor, partnership, and days waiting.",
        "7. Watch-only — no drafts until the CEO says `draft these`.",
        "",
        "## Chunks (newest first)",
        "",
    ]
    for chunk in chunks:
        lines.append(
            f"- chunk {chunk.index}: `{chunk.label}` — "
            f"search mail where last activity falls in this range"
        )
    lines += [
        "",
        "## Completion",
        "",
        "When all chunks are done, write one consolidated card to `00-Watch/` as",
        "`mail-audit--<date>.md` and summarize: total owed threads, top items,",
        "noise excluded, and whether HubSpot tier data was available.",
        "",
        "End with: `Reply draft these when you want me to prepare actions.`",
        "",
    ]
    return "\n".join(lines)


def run_local(cfg: Config, *, window_days: int = 365, staleness_days: int = 7) -> tuple[List[WatchItem], Path]:
    """Audit owed replies from local exports across the full window."""
    concern = Concern(
        id="mail-audit",
        playbook="account-followup-recovery",
        enabled=True,
        params={
            "account": "*",
            "staleness": f"{staleness_days}d",
            "window": f"{window_days}d",
        },
    )
    threads = load_threads(cfg)
    items = _account_followup(concern, threads, cfg)
    return items, concern


def _audit_card(cfg: Config, items: List[WatchItem], window_days: int,
                staleness_days: int, source: str) -> str:
    lines = [
        f"# Mail audit: owed replies ({cfg.today.isoformat()})",
        "",
        "type: reminder-card",
        f"source: {source}",
        f"window: {window_days}d",
        f"staleness: {staleness_days}d",
        f"items: {len(items)}",
        "",
        "Remind/assign only. Say \"draft these\" if you want draft-only replies prepared.",
        "",
    ]
    ranked = sorted(items, key=lambda i: i.waiting_days or 0, reverse=True)
    for n, item in enumerate(ranked, 1):
        lines.append(f"## {n}. {item.title}")
        if item.waiting_days is not None:
            lines.append(f"- waiting: {item.waiting_days}d")
        lines += [
            f"- why: {item.reason}",
            f"- action: {item.suggested_action}",
        ]
        if item.detail:
            lines.append(f"- context: {item.detail}")
        lines.append("")
    if not ranked:
        lines.append("_No owed replies in this window on exported data._")
        lines.append("")
    return "\n".join(lines)


def run(cfg: Config, *, window: str = "365d", staleness: str = "7d",
        chunk_days: int = 30) -> List[Path]:
    """Write audit manifest (+ local export card when data exists)."""
    ensure_dirs(cfg)
    window_days = _days_param(window, 365)
    staleness_days = _days_param(staleness, 7)
    chunks = build_chunks(cfg.today, window_days, chunk_days)
    written: List[Path] = []

    manifest_path = cfg.watch_dir / f"audit-manifest--{cfg.today.isoformat()}.md"
    manifest_path.write_text(
        _manifest(cfg, window_days, staleness_days, chunk_days, chunks),
        encoding="utf-8",
    )
    written.append(manifest_path)

    items, _ = run_local(cfg, window_days=window_days, staleness_days=staleness_days)
    if items:
        card_path = cfg.watch_dir / f"mail-audit--{cfg.today.isoformat()}.md"
        card_path.write_text(
            _audit_card(cfg, items, window_days, staleness_days, "local-export"),
            encoding="utf-8",
        )
        written.append(card_path)

    return written
