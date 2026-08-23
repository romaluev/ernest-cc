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
import re
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
    category: str = ""
    participants: List[str] = field(default_factory=list)
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
    summary = body[:280]
    try:
        from .thread_reader import parse_markdown
        conv = parse_markdown(path)
        if conv and conv.message_count:
            summary = conv.excerpt(280) or summary
    except ImportError:
        pass
    return Thread(
        id=path.stem,
        contact=header.get("contact", ""),
        company=header.get("company", ""),
        last_inbound=_parse_date(header.get("last_inbound", "")),
        last_outbound=_parse_date(header.get("last_outbound", "")),
        status=header.get("status", ""),
        intent=header.get("intent", "").lower(),
        subject=header.get("subject", ""),
        summary=summary,
        category=header.get("category", "").lower(),
        participants=[p.strip() for p in header.get("participants", "").split(",") if p.strip()],
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
            category=str(rec.get("category", "")).lower(),
            participants=[str(p).strip() for p in rec.get("participants", []) if str(p).strip()],
            source=str(rec.get("source", "local-export")),
            origin=str(path),
        ))
    return out


def load_threads(cfg: Config) -> List[Thread]:
    from .thread_reader import conversation_to_thread, load_all

    threads: List[Thread] = []
    seen: set[str] = set()
    mail_dir = cfg.data_dir / "mail"
    if mail_dir.is_dir():
        for path in sorted(mail_dir.iterdir()):
            try:
                if path.suffix.lower() == ".md":
                    thread = _parse_md_thread(path)
                    if thread:
                        threads.append(thread)
                        seen.add(thread.id)
                elif path.suffix.lower() == ".json":
                    for thread in _parse_json_threads(path):
                        threads.append(thread)
                        seen.add(thread.id)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
    for conv in load_all(cfg).values():
        if conv.thread_id in seen:
            continue
        if conv.message_count == 0:
            continue
        threads.append(conversation_to_thread(conv))
        seen.add(conv.thread_id)
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


# --------------------------------------------------------------------------- #
# LinkedIn inbound (invitations)
# --------------------------------------------------------------------------- #

@dataclass
class Invitation:
    """One pending inbound connection invitation.

    Optional integer fields are Optional ON PURPOSE. `None` means "we did not
    look" and must never be scored as evidence; `0` means "we looked and there
    were none". Missing != 0 — the ingest rung decides which one you get, and
    the LinkedIn archive export carries neither, so both stay None there.
    """
    name: str
    public_url: str = ""
    urn: str = ""
    headline: str = ""
    company: str = ""
    location: str = ""
    note: str = ""
    sent_at: Optional[date] = None
    mutual_connections: Optional[int] = None
    connections: Optional[int] = None
    invitation_type: str = "connect"   # connect | companyFollow | newsletterSubscribe
    direction: str = "received"        # received | sent
    source: str = "local-export"

    def days_waiting(self, today: date) -> int:
        if self.sent_at is None:
            return 0
        return max(0, (today - self.sent_at).days)

    @property
    def key(self) -> str:
        from .grading import identity_key
        return identity_key(self.public_url, self.urn, self.name)


# The archive export stamps dates several ways depending on locale and category;
# the live-DOM rung emits ISO. Normalizing exotic formats ("1 month ago") is the
# ADAPTER's job — the engine accepts the handful of shapes that arrive verbatim.
_INVITE_DATE_FORMATS = (
    "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S %Z", "%m/%d/%y, %I:%M %p", "%m/%d/%Y", "%d %b %Y", "%b %d, %Y",
)


def _parse_date_loose(value: str) -> Optional[date]:
    text = (value or "").strip().replace("Z", "").strip()
    if not text:
        return None
    for fmt in _INVITE_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:  # last resort: a leading ISO date inside a longer stamp
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _opt_int(value: str) -> Optional[int]:
    """'' -> None (unknown), '0' -> 0 (looked, found none). The distinction matters."""
    text = (value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


# LinkedIn's own archive uses spaced Title Case headers ("Sent At", "From",
# "Inviter Profile URL"); the live-DOM rung writes snake_case. Accept both
# rather than making the adapter guess which shape the engine wants.
_INVITE_ALIASES = {
    "name": ("name", "from", "inviter", "invitername", "fromname", "displayname"),
    "public_url": ("public_url", "publicurl", "inviterprofileurl", "profileurl", "url", "linkedin"),
    "urn": ("urn", "memberurn", "inviterurn", "entityurn"),
    "headline": ("headline", "title", "occupation"),
    "company": ("company", "organization", "currentcompany"),
    "location": ("location", "geo", "country"),
    "note": ("note", "message", "invitationmessage", "connectionrequestnote"),
    "sent_at": ("sent_at", "sentat", "senttime", "date", "invitedat", "receivedat"),
    "mutual_connections": ("mutual_connections", "mutualconnections", "mutuals", "sharedconnections"),
    "connections": ("connections", "connectioncount", "networksize"),
    "invitation_type": ("invitation_type", "invitationtype", "type"),
    "direction": ("direction", "sentorreceived"),
}


def _pick(row: dict, field_name: str) -> str:
    norm = {re.sub(r"[^a-z0-9]", "", (k or "").lower()): v for k, v in row.items()}
    for alias in _INVITE_ALIASES[field_name]:
        val = norm.get(re.sub(r"[^a-z0-9]", "", alias))
        if val:
            return str(val).strip()
    return ""


def load_invitations(cfg: Config) -> List[Invitation]:
    """Read every `data/linkedin/*.csv` export. Received `connect` invites only.

    Company follows and newsletter subscriptions are not invitations to triage —
    LinkedIn returns them from the same surface and they would inflate every
    count on the report if they were not dropped here.
    """
    li_dir = cfg.data_dir / "linkedin"
    if not li_dir.is_dir():
        return []
    # Which RUNG produced this is a fact the adapter recorded, not something to
    # infer from a filename. A month-old snapshot and a live read must not both
    # print `source: local-export` on the report.
    default_source = "local-export"
    try:
        default_source = json.loads(
            (li_dir / ".ingest.json").read_text(encoding="utf-8")).get("source") or default_source
    except (OSError, ValueError):
        pass
    out: List[Invitation] = []
    seen: set = set()
    for path in sorted(li_dir.glob("*.csv")):
        if "connection" in path.name.lower() and "invitation" not in path.name.lower():
            continue  # Connections.csv is the network, not the queue
        source = default_source
        try:
            with path.open(encoding="utf-8-sig", newline="") as fh:
                for row in csv.DictReader(fh):
                    direction = (_pick(row, "direction") or "received").lower()
                    if direction.startswith("sent") or direction == "outgoing":
                        continue
                    itype = (_pick(row, "invitation_type") or "connect").strip()
                    if itype and itype.lower() not in ("connect", "connection", "invitation", ""):
                        continue
                    name = _pick(row, "name")
                    url = _pick(row, "public_url")
                    if not (name or url):
                        continue
                    inv = Invitation(
                        name=name,
                        public_url=url,
                        urn=_pick(row, "urn"),
                        headline=_pick(row, "headline"),
                        company=_pick(row, "company"),
                        location=_pick(row, "location"),
                        note=_pick(row, "note"),
                        sent_at=_parse_date_loose(_pick(row, "sent_at")),
                        mutual_connections=_opt_int(_pick(row, "mutual_connections")),
                        connections=_opt_int(_pick(row, "connections")),
                        invitation_type=itype or "connect",
                        direction="received",
                        source=source,
                    )
                    # Same human, two identifier shapes (slug vs ACoAA... URN).
                    # Keying on either alone double-counts them — see identity_key.
                    if inv.key in seen:
                        continue
                    seen.add(inv.key)
                    out.append(inv)
        except (OSError, ValueError):
            continue
    return out
