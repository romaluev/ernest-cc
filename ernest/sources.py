"""Read-only data sources for the engine.

Priority order, matching the product contract:
  1. VPS brain (canonical) - read via MCP at the Claude layer, not here.
  2. Local MCP connectors - same.
  3. Local exported files under `data/` - this module.

This module only handles tier 3 (local exports) so the engine is fully
functional offline. Everything it returns is tagged `source: local-export`.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from .config import Config


@dataclass
class Thread:
    id: str
    contact: str
    company: str
    last_inbound: Optional[date]
    last_outbound: Optional[date]
    status: str = ""
    intent: str = ""
    subject: str = ""
    summary: str = ""
    source: str = "local-export"
    origin: str = ""

    @property
    def owed(self) -> bool:
        """CEO owes a reply: there is an inbound and no later outbound."""
        if self.last_inbound is None:
            return False
        if self.last_outbound is None:
            return True
        return self.last_outbound < self.last_inbound

    def days_waiting(self, today: date) -> int:
        if self.last_inbound is None:
            return 0
        return max(0, (today - self.last_inbound).days)


@dataclass
class Contact:
    email: str
    name: str
    company: str
    tier: str = ""
    last_touch: Optional[date] = None
    next_action: str = ""
    source: str = "local-export"


def _parse_date(value: str) -> Optional[date]:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_md_thread(path: Path) -> Optional[Thread]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    header: dict[str, str] = {}
    body_start = 0
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped.startswith("#"):
            continue
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
    if not header:
        return None
    body = " ".join("\n".join(lines[body_start:]).split())
    return Thread(
        id=path.stem,
        contact=header.get("contact", ""),
        company=header.get("company", ""),
        last_inbound=_parse_date(header.get("last_inbound", "")),
        last_outbound=_parse_date(header.get("last_outbound", "")),
        status=header.get("status", ""),
        intent=header.get("intent", "").lower(),
        subject=header.get("subject", ""),
        summary=body[:280],
        source=header.get("source", "local-export"),
        origin=str(path),
    )


def _parse_json_threads(path: Path) -> List[Thread]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    records = raw if isinstance(raw, list) else [raw]
    out: List[Thread] = []
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            continue
        out.append(Thread(
            id=str(rec.get("id") or f"{path.stem}-{i}"),
            contact=str(rec.get("contact", "")),
            company=str(rec.get("company", "")),
            last_inbound=_parse_date(str(rec.get("last_inbound", ""))),
            last_outbound=_parse_date(str(rec.get("last_outbound", ""))),
            status=str(rec.get("status", "")),
            intent=str(rec.get("intent", "")).lower(),
            subject=str(rec.get("subject", "")),
            summary=" ".join(str(rec.get("summary", rec.get("snippet", ""))).split())[:280],
            source=str(rec.get("source", "local-export")),
            origin=str(path),
        ))
    return out


def load_threads(cfg: Config) -> List[Thread]:
    mail_dir = cfg.data_dir / "mail"
    if not mail_dir.is_dir():
        return []
    threads: List[Thread] = []
    for path in sorted(mail_dir.iterdir()):
        try:
            if path.suffix.lower() == ".md":
                thread = _parse_md_thread(path)
                if thread:
                    threads.append(thread)
            elif path.suffix.lower() == ".json":
                threads.extend(_parse_json_threads(path))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return threads


def load_contacts(cfg: Config) -> List[Contact]:
    hub_dir = cfg.data_dir / "hubspot"
    if not hub_dir.is_dir():
        return []
    contacts: List[Contact] = []
    for path in sorted(hub_dir.glob("*.csv")):
        try:
            with path.open(encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh):
                    name = " ".join(p for p in (row.get("firstname", ""), row.get("lastname", "")) if p).strip()
                    contacts.append(Contact(
                        email=row.get("email", "").strip(),
                        name=name or row.get("email", "").strip(),
                        company=row.get("company", "").strip(),
                        tier=row.get("tier", "").strip(),
                        last_touch=_parse_date(row.get("last_touch", "")),
                        next_action=row.get("next_action", "").strip(),
                    ))
        except (OSError, ValueError):
            continue
    return contacts
