"""Ambient watch: turn standing concerns + sources into reminder/assign cards.

Detection is deterministic and remind-only. Cards never contain drafts; they
state what slipped or what to assign, and the suggested next action.

Playbooks (mapped to the CEO's real use-cases):
  - account-followup-recovery : dropped follow-ups (optionally priority-tier scoped)
  - inbox-prospect-followup   : inbound prospects needing a first follow-up
  - add-collaborator          : ensure a teammate is on matching threads (B2B, etc.)
  - candidate-followup        : hiring candidates in the inbox to assign reach-out
  - list-sync                 : reconcile email contacts against a HubSpot list / sheet
  - sourcing-pipeline         : manage a list of partnership/hire targets to contact
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

from .concerns import Concern, load as load_concerns
from .config import Config, ensure_dirs
from .sources import Thread, load_contacts, load_threads

_TARGET_INTENTS = {"partnership", "sales", "investor", "press", "hire", "inbound"}


def _days_param(value: str, default: int) -> int:
    match = re.search(r"(\d+)", value or "")
    return int(match.group(1)) if match else default


def _csv_list(value: str) -> List[str]:
    return [p.strip() for p in (value or "").split(",") if p.strip()]


@dataclass
class WatchItem:
    concern_id: str
    title: str
    reason: str
    suggested_action: str
    detail: str = ""
    waiting_days: Optional[int] = None
    thread: Optional[Thread] = None


def _company_tier_map(cfg: Config) -> Dict[str, str]:
    return {c.company.lower(): c.tier.lower() for c in load_contacts(cfg) if c.company}


def _account_followup(concern: Concern, threads: List[Thread], cfg: Config) -> List[WatchItem]:
    staleness = _days_param(concern.params.get("staleness", ""), 7)
    window = _days_param(concern.params.get("window", ""), 0)
    account = concern.params.get("account", "*").strip()
    tiers = {t.lower() for t in _csv_list(concern.params.get("priority_tiers", ""))}
    tier_map = _company_tier_map(cfg) if tiers else {}
    items: List[WatchItem] = []
    for t in threads:
        waiting = t.days_waiting(cfg.today)
        if not (t.owed and waiting >= staleness):
            continue
        if window and waiting > window:
            continue
        if account not in ("", "*") and account.lower() not in (t.company + " " + t.contact).lower():
            continue
        if tiers and tier_map.get(t.company.lower(), "") not in tiers:
            continue
        scope = "important " if tiers else ""
        items.append(WatchItem(
            concern.id, f"{t.contact or 'Unknown'} - {t.company or 'Unknown'}",
            f"Inbound {waiting}d ago with no reply (threshold {staleness}d).",
            f"Reply to this {scope}contact to keep the thread alive.",
            detail=t.summary or t.status, waiting_days=waiting, thread=t,
        ))
    return items


def _inbox_prospect(concern: Concern, threads: List[Thread], cfg: Config) -> List[WatchItem]:
    wanted = concern.params.get("intent", "").lower()
    window = _days_param(concern.params.get("window", ""), 90)
    items: List[WatchItem] = []
    for t in threads:
        intent_ok = (not wanted) or (t.intent == wanted) or (t.intent in _TARGET_INTENTS)
        if t.owed and intent_ok and t.days_waiting(cfg.today) <= window:
            items.append(WatchItem(
                concern.id, f"{t.contact or 'Unknown'} - {t.company or 'Unknown'}",
                f"Inbound {t.intent or 'prospect'} lead waiting {t.days_waiting(cfg.today)}d.",
                "Qualify and send a first follow-up.",
                detail=t.summary or t.status, waiting_days=t.days_waiting(cfg.today), thread=t,
            ))
    return items


def _add_collaborator(concern: Concern, threads: List[Thread], cfg: Config) -> List[WatchItem]:
    who = concern.params.get("collaborator", "").strip()
    category = concern.params.get("category", "").strip().lower()
    items: List[WatchItem] = []
    for t in threads:
        if category and t.category != category:
            continue
        if who and any(who.lower() in p.lower() for p in t.participants):
            continue
        items.append(WatchItem(
            concern.id, f"{t.company or t.contact or 'Thread'} - {t.subject or 'thread'}",
            f"{category.upper() or 'Key'} thread without {who or 'the collaborator'}.",
            f"Add {who or 'the collaborator'} to this thread so the follow-up isn't dropped.",
            detail=f"participants: {', '.join(t.participants) or 'unknown'}", thread=t,
        ))
    return items


def _candidate_followup(concern: Concern, threads: List[Thread], cfg: Config) -> List[WatchItem]:
    role = concern.params.get("role", "candidate")
    assignees = concern.params.get("assignees", "").strip()
    window = _days_param(concern.params.get("window", ""), 180)
    items: List[WatchItem] = []
    for t in threads:
        is_candidate = t.category == "candidate" or t.intent == "hire"
        if is_candidate and t.owed and t.days_waiting(cfg.today) <= window:
            items.append(WatchItem(
                concern.id, f"{t.contact or 'Candidate'} - {role}",
                f"Inbound {role} candidate waiting {t.days_waiting(cfg.today)}d, no follow-up.",
                f"Assign reach-out to {assignees or 'the hiring owner'}.",
                detail=t.summary or t.status, waiting_days=t.days_waiting(cfg.today), thread=t,
            ))
    return items


def _list_sync(concern: Concern, threads: List[Thread], cfg: Config) -> List[WatchItem]:
    category = concern.params.get("category", "").strip().lower()
    match_key = concern.params.get("match_key", "company").strip()
    target_key = concern.params.get("target_key", "company").strip()
    target_rel = concern.params.get("target", "").strip()
    list_name = concern.params.get("list_name", target_rel or "the target list")
    target_path = cfg.profile_dir / target_rel
    present: set[str] = set()
    if target_path.is_file():
        with target_path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                value = (row.get(target_key) or "").strip().lower()
                if value:
                    present.add(value)
    items: List[WatchItem] = []
    for t in threads:
        if category and t.category != category:
            continue
        key_value = (getattr(t, match_key, "") or "").strip()
        if key_value and key_value.lower() not in present:
            items.append(WatchItem(
                concern.id, f"{t.contact or 'Contact'} - {t.company or key_value}",
                f"In email ({category or 'contact'}) but missing from {list_name}.",
                f"Add to {list_name} to keep email and the list in sync.",
                detail=t.subject or t.status,
            ))
    return items


def _sourcing_pipeline(concern: Concern, threads: List[Thread], cfg: Config) -> List[WatchItem]:
    source_rel = concern.params.get("source", "").strip()
    purpose = concern.params.get("purpose", "outreach")
    done = {"contacted", "done", "reached", "skip", "skipped"}
    source_path = cfg.profile_dir / source_rel
    items: List[WatchItem] = []
    if not source_path.is_file():
        return items
    with source_path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            status = (row.get("status") or "new").strip().lower()
            if status in done:
                continue
            name = (row.get("name") or "").strip()
            link = (row.get("linkedin") or "").strip()
            note = (row.get("note") or "").strip()
            row_purpose = (row.get("purpose") or purpose).strip()
            items.append(WatchItem(
                concern.id, f"{name or 'Target'} ({row_purpose})",
                f"Sourced {row_purpose} target not yet contacted.",
                "Review and assign outreach.",
                detail=" - ".join(p for p in (link, note) if p),
            ))
    return items


def _task_tracker(concern: Concern, threads: List[Thread], cfg: Config) -> List[WatchItem]:
    source_rel = concern.params.get("source", "").strip()
    done = {"done", "closed", "cancelled", "canceled"}
    source_path = cfg.profile_dir / source_rel
    items: List[WatchItem] = []
    if not source_path.is_file():
        return items
    with source_path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            status = (row.get("status") or "open").strip().lower()
            if status in done:
                continue
            task = (row.get("task") or "").strip()
            owner = (row.get("owner") or "unassigned").strip()
            due = (row.get("due") or "").strip()
            origin = (row.get("source") or "").strip()
            overdue = False
            try:
                overdue = bool(due) and datetime.strptime(due, "%Y-%m-%d").date() < cfg.today
            except ValueError:
                overdue = False
            flag = "OVERDUE" if overdue else status.upper()
            items.append(WatchItem(
                concern.id, f"[{flag}] {task or 'Task'} -> {owner}",
                ("Overdue task" if overdue else "Open task") + f" owned by {owner}"
                + (f", due {due}" if due else "") + ".",
                f"Track to done; nudge {owner} if stalled.",
                detail=origin,
            ))
    return items


_PLAYBOOKS = {
    "account-followup-recovery": _account_followup,
    "inbox-prospect-followup": _inbox_prospect,
    "add-collaborator": _add_collaborator,
    "candidate-followup": _candidate_followup,
    "list-sync": _list_sync,
    "sourcing-pipeline": _sourcing_pipeline,
    "task-tracker": _task_tracker,
}


def detect(cfg: Config) -> List[WatchItem]:
    threads = load_threads(cfg)
    items: List[WatchItem] = []
    for concern in load_concerns(cfg):
        if not concern.enabled:
            continue
        handler = _PLAYBOOKS.get(concern.playbook)
        if handler:
            items.extend(handler(concern, threads, cfg))
    return items


def _card(cfg: Config, concern_id: str, items: List[WatchItem]) -> str:
    lines = [
        f"# Watch: {concern_id} ({cfg.today.isoformat()})",
        "",
        "type: reminder-card",
        "source: local-export",
        f"items: {len(items)}",
        "",
        "Remind/assign only. Say \"draft these\" if you want draft-only outreach prepared.",
        "",
    ]
    for n, item in enumerate(items, 1):
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
    return "\n".join(lines)


def run(cfg: Config) -> List[Path]:
    ensure_dirs(cfg)
    items = detect(cfg)
    by_concern: Dict[str, List[WatchItem]] = {}
    for item in items:
        by_concern.setdefault(item.concern_id, []).append(item)
    written: List[Path] = []
    for concern_id, group in by_concern.items():
        path = cfg.watch_dir / f"{concern_id}--{cfg.today.isoformat()}.md"
        path.write_text(_card(cfg, concern_id, group), encoding="utf-8")
        written.append(path)
    return written
