"""Deep mail audit: chunked sweep for owed replies over a long window.

Daily `ernest watch` uses short staleness defaults (7d) and is cheap. A CEO
"full year audit" needs an explicit window, date-bucketed search, and a rule to
finish every bucket before summarizing — otherwise live MCP runs stop after the
first recent page of results.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

from .concerns import Concern
from .config import Config, ensure_dirs
from .sources import load_threads
from .watch import WatchItem, _account_followup

COLD_START_DAYS = 365     # first-ever sweep covers the last 12 months
OVERLAP_DAYS = 3          # re-cover a few recent days each run (catch late arrivals)


def _days_param(value: str, default: int) -> int:
    match = re.search(r"(\d+)", value or "")
    return int(match.group(1)) if match else default


def _sweep_state_path(cfg: Config) -> Path:
    return cfg.logs_dir / "sweep-state.json"


def read_last_sweep(cfg: Config) -> Optional[date]:
    p = _sweep_state_path(cfg)
    if not p.is_file():
        return None
    try:
        return date.fromisoformat(json.loads(p.read_text(encoding="utf-8"))["last_sweep"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None


def record_sweep(cfg: Config) -> None:
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)
    _sweep_state_path(cfg).write_text(
        json.dumps({"last_sweep": cfg.today.isoformat()}), encoding="utf-8")


def resolve_window_days(cfg: Config, requested: str = "") -> Tuple[int, bool]:
    """Decide the lookback window. Explicit request wins. Otherwise: first-ever
    sweep = 12 months (cold start); subsequent = since the last sweep (+overlap).
    Returns (window_days, is_cold_start)."""
    if requested and requested.strip():
        return _days_param(requested, COLD_START_DAYS), False
    last = read_last_sweep(cfg)
    if last is None:
        return COLD_START_DAYS, True
    delta = (cfg.today - last).days
    return max(7, delta + OVERLAP_DAYS), False


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
              chunks: List[AuditChunk], cold_start: bool = False) -> str:
    lines = [
        f"# Follow-up sweep manifest ({cfg.today.isoformat()})",
        "",
        "type: audit-manifest",
        f"window_days: {window_days}",
        f"cold_start: {'true (first sweep — full 12 months)' if cold_start else 'false (incremental since last sweep)'}",
        f"staleness_days: {staleness_days}",
        f"chunk_days: {chunk_days}",
        f"chunks_total: {len(chunks)}",
        "",
        "## Rules — search WIDE, then CROSS-CHECK for resolution",
        "",
        "1. Process **every chunk below** before summarizing. Do **not** stop after the first",
        "   page/recent cluster, and do not ask the CEO to continue unless a connector is blocked.",
        "2. **Find candidates across ALL connected tools**, not just mail: Inbox + Sent",
        "   (they wrote last, you never replied), HubSpot (quiet/overdue deals, open tasks),",
        "   Slack (open asks/threads you owe), Calendar (promised but unscheduled). Dedupe by",
        "   contact/company/thread across tools.",
        "3. **Before flagging anything as dropped, CROSS-CHECK every other tool for whether it",
        "   was already handled elsewhere:**",
        "   - HubSpot: is the deal advanced/closed, or is there recent logged activity?",
        "   - Slack: was it resolved/confirmed in a thread or DM (search the company, person, topic)?",
        "   - Calendar: did the meeting actually happen?",
        "   - Mail: did you (or a teammate) reply in a different thread?",
        "   If it was handled elsewhere, **DROP it from the dropped-follow-up list.**",
        "4. **Stale CRM:** if it was resolved elsewhere but HubSpot doesn't reflect it (deal",
        "   stage, next-step, or activity), PROPOSE a HubSpot update as a reviewable, draft-first",
        "   action (never write to the CRM automatically).",
        "5. Only surface **genuinely-open** items. Exclude noise (newsletters, job-seeker intros,",
        "   cold vendor outreach) unless the CEO asked to include them.",
        "6. Rank by revenue, investor, partnership, relationship tier, and days waiting.",
        "7. Watch-only — no sends, no live CRM writes; drafts/CRM-proposals only on `draft these`.",
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


def run(cfg: Config, *, window: str = "", staleness: str = "7d",
        chunk_days: int = 30) -> List[Path]:
    """Write the sweep manifest (+ local export card when data exists).

    With no explicit `window`, the lookback is chosen automatically: the first-ever
    sweep covers 12 months (cold start); later runs cover only the time since the
    last sweep (plus a small overlap), so repeat sweeps are fast.
    """
    ensure_dirs(cfg)
    window_days, cold_start = resolve_window_days(cfg, window)
    staleness_days = _days_param(staleness, 7)
    chunks = build_chunks(cfg.today, window_days, chunk_days)
    written: List[Path] = []

    manifest_path = cfg.watch_dir / f"audit-manifest--{cfg.today.isoformat()}.md"
    manifest_path.write_text(
        _manifest(cfg, window_days, staleness_days, chunk_days, chunks, cold_start=cold_start),
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

    record_sweep(cfg)   # remember 'today' so the next sweep is incremental
    return written
