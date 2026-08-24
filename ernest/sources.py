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
from typing import List, Optional, Tuple

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
    open_deal: bool = False       # live money on the relationship
    won_revenue: float = 0.0      # closed-won total
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
                        open_deal=(row.get("open_deal", "") or "").strip().lower()
                        in ("1", "true", "yes", "y", "open"),
                        won_revenue=_opt_float(row.get("won_revenue", "")),
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


def _opt_float(value: str) -> float:
    """Absent means 0, not unknown — a missing revenue column is not evidence
    of revenue. Unlike counts, 0 and blank mean the same thing for money."""
    text = re.sub(r"[^0-9.\-]", "", (value or "").strip())
    try:
        return float(text) if text else 0.0
    except ValueError:
        return 0.0


def _opt_int(value: str) -> Optional[int]:
    """'' -> None (unknown), '0' -> 0 (looked, found none). The distinction matters."""
    text = (value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        n = int(float(text))
    except ValueError:
        return None
    # Negative counts cannot happen; a negative means the export is corrupt, and
    # "corrupt" must read as unknown rather than as an extreme value that would
    # score someone as a thin-network spammer.
    return n if n >= 0 else None


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
        name = path.name.lower()
        # ALLOW-LIST, not a deny-list. A real LinkedIn export drops Invitations,
        # Connections, and messages side by side in one folder; excluding only
        # the names we happened to think of let messages.csv load as invitations
        # and silently inflate the queue.
        if not (name.startswith("invitation") or "invitations" in name
                or name == "invites.csv"):
            continue
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
                    #
                    # But a NAME is not an identifier. Two different people can
                    # share a display name, and deduping those together silently
                    # deletes one of them. Only collapse rows that share a real
                    # identifier; fall back to the whole row otherwise.
                    key = inv.key
                    if key.startswith("name:"):
                        key = (f"{key}|{inv.headline}|{inv.company}|"
                               f"{inv.sent_at}|{inv.note[:60]}")
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(inv)
        except (OSError, ValueError):
            continue
    return out


# --------------------------------------------------------------------------- #
# LinkedIn inbound (direct messages)
# --------------------------------------------------------------------------- #

@dataclass
class LIMessage:
    at: Optional[date]
    sender: str
    direction: str      # inbound | outbound
    body: str = ""
    subject: str = ""


@dataclass
class Conversation:
    """One LinkedIn message thread.

    Unlike an invitation, a thread has HISTORY, so the first question is not
    "who is this" but "am I the one holding this up". Everything else follows
    from that.
    """
    id: str
    counterparty: str
    counterparty_url: str = ""
    subject: str = ""
    folder: str = ""            # INBOX | ARCHIVE | SPAM (LinkedIn's own label)
    messages: List[LIMessage] = field(default_factory=list)
    participants: List[str] = field(default_factory=list)
    source: str = "local-export"

    @property
    def is_group(self) -> bool:
        """More than one person on the other side. Treating a group thread as a
        one-to-one conversation attributes everything to whoever wrote first."""
        return len({p for p in self.participants if p}) > 1

    @property
    def inbound(self) -> List[LIMessage]:
        return [m for m in self.messages if m.direction == "inbound"]

    @property
    def last_inbound(self) -> Optional[date]:
        return max((m.at for m in self.inbound if m.at), default=None)

    @property
    def last_outbound(self) -> Optional[date]:
        return max((m.at for m in self.messages
                    if m.direction == "outbound" and m.at), default=None)

    @property
    def owed(self) -> bool:
        """They wrote last and we never answered. The whole triage hinges on it."""
        if self.last_inbound is None:
            return False
        if self.last_outbound is None:
            return True
        return self.last_outbound < self.last_inbound

    @property
    def ever_replied(self) -> bool:
        """A thread we have answered before is a relationship, not cold outreach."""
        return self.last_outbound is not None

    @property
    def opener(self) -> str:
        """Their first message — what a cold sender actually pitched."""
        first = sorted(self.inbound, key=lambda m: (m.at or date.min))
        return first[0].body if first else ""

    @property
    def text(self) -> str:
        return " ".join(m.body for m in self.inbound)

    def days_waiting(self, today: date) -> int:
        return max(0, (today - self.last_inbound).days) if self.last_inbound else 0


_MSG_ALIASES = {
    "id": ("conversationid", "conversation_id", "threadid", "id"),
    "subject": ("subject", "conversationtitle", "title"),
    "sender": ("from", "sender", "sendername"),
    "sender_url": ("senderprofileurl", "sender_profile_url", "fromprofileurl"),
    "recipient": ("to", "recipient", "recipientname"),
    "recipient_url": ("recipientprofileurls", "recipientprofileurl", "toprofileurl"),
    "at": ("date", "sentat", "senttime", "datesent"),
    "body": ("content", "body", "message"),
    "folder": ("folder", "mailbox"),
}


def _pick_msg(row: dict, field_name: str) -> str:
    norm = {re.sub(r"[^a-z0-9]", "", (k or "").lower()): v for k, v in row.items()}
    for alias in _MSG_ALIASES[field_name]:
        val = norm.get(re.sub(r"[^a-z0-9]", "", alias))
        if val:
            return str(val).strip()
    return ""


def _owner_from_memory(cfg: Config) -> str:
    """The account owner's name, from memory/ceo-persona.md."""
    try:
        text = (cfg.memory_dir / "ceo-persona.md").read_text(encoding="utf-8")
    except OSError:
        return ""
    for line in text.splitlines():
        m = re.match(r"\s*-\s*Name:\s*(.+)", line, re.I)
        if not m:
            continue
        # The shipped persona packs several fields onto one line
        # ("Sam Rivera. Role: CEO & Co-Founder, Northwind."), so keep only the
        # name itself — matching on the whole line silently matches nobody, and
        # a silent no-match inverts the direction of every message.
        name = re.split(r"[.,;|]| - |\bRole\b", m.group(1).strip(), maxsplit=1)[0].strip()
        if name and "(" not in name:
            return name.lower()
    return ""


_LAST_OWNER = ""
_LAST_OWNER_SOURCE = "unknown"


def last_owner() -> Tuple[str, str]:
    """Who the last load treated as "us", and how that was decided.

    Reported on the card because getting it wrong inverts every message in the
    inbox while still producing a report that looks entirely normal.
    """
    return _LAST_OWNER, _LAST_OWNER_SOURCE


def load_conversations(cfg: Config, owner_names: Optional[List[str]] = None) -> List[Conversation]:
    """Read `data/linkedin/messages*.csv` into threads.

    LinkedIn's archive ships one ROW PER MESSAGE with FROM/TO on each, so the
    direction of every message is derived by comparing the sender against the
    account owner rather than trusted from a column — the export has no such
    column. Owner identity comes from `memory/ceo-persona.md`, falling back to
    whoever sends the most messages across the file, which is the owner by
    construction in an inbox export.
    """
    li_dir = cfg.data_dir / "linkedin"
    if not li_dir.is_dir():
        return []
    default_source = "local-export"
    try:
        default_source = json.loads(
            (li_dir / ".ingest.json").read_text(encoding="utf-8")).get("source") or default_source
    except (OSError, ValueError):
        pass

    rows: List[dict] = []
    for path in sorted(li_dir.glob("*.csv")):
        name = path.name.lower()
        if "message" not in name and "conversation" not in name:
            continue
        try:
            with path.open(encoding="utf-8-sig", newline="") as fh:
                rows.extend(list(csv.DictReader(fh)))
        except (OSError, ValueError):
            continue
    if not rows:
        return []

    # Check BOTH sides. Someone who only ever receives is still the owner — an
    # inbox full of unanswered mail is exactly the case this has to handle.
    appearing = {(_pick_msg(r, "sender") or "").strip().lower() for r in rows}
    appearing |= {(_pick_msg(r, "recipient") or "").strip().lower() for r in rows}
    appearing.discard("")

    owners = {n.strip().lower() for n in (owner_names or []) if n and n.strip()}
    if not owners:
        owners = {n for n in (_owner_from_memory(cfg),) if n}
    configured = set(owners)

    # A configured name that appears NOWHERE in the export is not aconfiguration choice,
    # it is a mismatch — and trusting it inverts the direction of every message,
    # so the owner's own replies come back as unanswered inbound mail. That is
    # the single most damaging failure this module has, and it looks like a
    # working report. Verify the name is really in the data before trusting it.
    trusted_config = bool(owners and (owners & appearing))
    if owners and not trusted_config:
        owners = set()
    if not owners:
        # Fallback: the owner is whoever appears in the MOST DISTINCT THREADS,
        # not whoever sent the most messages. A single persistent spammer can
        # out-message the account owner inside one thread — and misdetecting the
        # owner inverts the direction of every message in the export, which
        # turns their own replies into inbound mail and flips the whole report.
        threads: dict = {}
        for row in rows:
            who = _pick_msg(row, "sender").lower()
            cid = _pick_msg(row, "id") or _pick_msg(row, "sender_url")
            if who:
                threads.setdefault(who, set()).add(cid)
        if threads:
            best = max(threads, key=lambda w: (len(threads[w]), w))
            owners = {best}

    # Record it unconditionally — the card reports it, and a stale value here is
    # a report that names the wrong person as "us".
    globals()["_LAST_OWNER"] = sorted(owners)[0] if owners else ""
    globals()["_LAST_OWNER_SOURCE"] = (
        "memory/ceo-persona.md" if trusted_config
        else "inferred from the export" if owners else "unknown")

    convos: dict = {}
    for row in rows:
        sender = _pick_msg(row, "sender")
        recipient = _pick_msg(row, "recipient")
        outbound = sender.lower() in owners
        other = recipient if outbound else sender
        other_url = _pick_msg(row, "recipient_url") if outbound else _pick_msg(row, "sender_url")
        other_url = (other_url or "").split("|")[0].split(";")[0].strip()
        cid = _pick_msg(row, "id") or (identity_key_for(other_url, other) if (other_url or other) else "")
        if not cid:
            continue
        convo = convos.get(cid)
        if convo is None:
            convo = convos[cid] = Conversation(
                id=cid, counterparty=other, counterparty_url=other_url,
                subject=_pick_msg(row, "subject"),
                folder=(_pick_msg(row, "folder") or "INBOX").upper(),
                source=default_source)
        if not outbound and other and other not in convo.participants:
            convo.participants.append(other)
        if not convo.counterparty and other:
            convo.counterparty, convo.counterparty_url = other, other_url
        convo.messages.append(LIMessage(
            at=_parse_date_loose(_pick_msg(row, "at")),
            sender=sender or ("me" if outbound else other),
            direction="outbound" if outbound else "inbound",
            body=_pick_msg(row, "body"),
            subject=_pick_msg(row, "subject")))
    out: List[Conversation] = []
    for convo in convos.values():
        if not convo.inbound:
            continue
        if convo.is_group:
            # Name everyone rather than silently picking one. The counterparty
            # becomes whoever actually wrote the most, so value and triage still
            # attach to the person driving the thread.
            counts: dict = {}
            for m in convo.inbound:
                counts[m.sender] = counts.get(m.sender, 0) + 1
            if counts:
                convo.counterparty = max(counts, key=lambda k: (counts[k], k))
            others = [p for p in convo.participants if p != convo.counterparty]
            if others:
                convo.subject = (convo.subject or "") + \
                    f" [group thread with {len(convo.participants)}: " \
                    f"{', '.join(convo.participants[:4])}]"
        out.append(convo)
    return out


def identity_key_for(public_url: str = "", name: str = "") -> str:
    from .grading import identity_key
    return identity_key(public_url, "", name)
