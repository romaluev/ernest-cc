"""What a LinkedIn thread is actually worth, and what is buried inside it.

Triage answers "is this spam". This module answers the questions that follow:

    value_of()      who is this and what are they worth to us
    commitments()   what did WE promise and never deliver
    deadlines()     what has a clock on it, and has it already passed
    thread_state()  where does this conversation actually stand
    campaigns()     which of these are one outreach blast wearing many faces
    unify()         the same human across invitations, DMs, and the CRM
    diff_runs()     what changed since the last report

Everything here is value-weighted, because volume is the whole problem. An
unkept promise to a customer with an open deal and an unkept "I'll intro you"
to someone with no company are not the same object, and a report that lists
them together is a list, not a judgment.

Two rules the whole module rests on:

1. **Facts outrank inference.** A closed-won number or an open deal is a fact.
   "Their headline contains 'founder'" is a guess. They are weighted an order of
   magnitude apart and reported separately.
2. **Unknown is a state, not a low score.** When we genuinely cannot tell who
   someone is, that is recorded as `unknown` and caps their band — it never
   quietly averages into "medium". An unknown counterparty cannot make a
   commitment look worth chasing.

Standard library only, like the rest of the engine.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .config import Config
from .grading import _all_in, _any_in, _hay, _load_rubric, identity_key

# --------------------------------------------------------------------------- #
# Counterparty value
# --------------------------------------------------------------------------- #

# Facts about a real commercial relationship. These dominate on purpose: no
# amount of keyword matching should outrank an open deal.
VALUE_FACT_WEIGHTS = {
    "open_deal": 45.0,          # there is live money on this relationship
    "won_revenue": 40.0,        # scaled by log10 of the amount, see _revenue_points
    "crm_tier_1": 30.0,
    "crm_tier_other": 12.0,
    "prior_contact": 10.0,      # in the CRM at all, with a real touch
}

# Inference from what they wrote or how they describe themselves. Deliberately
# an order of magnitude smaller than the facts above.
VALUE_SIGNAL_WEIGHTS = {
    "archetype": 10.0,          # per buyer-archetype hit
    "vertical": 7.0,
    "platform_buyer": 10.0,
    "major_company": 12.0,
    "provider": 9.0,
    "seniority": 7.0,           # decision-maker title
    "intent": 9.0,              # per buying-intent phrase
    "mutuals": 4.0,             # single bump above the rubric floor
    "replied_before": 12.0,     # we chose to engage; that is our own signal
    "reply_depth": 3.0,         # per outbound message, capped
    "thread_depth": 1.5,        # per message, capped
}
REPLY_DEPTH_CAP = 5
THREAD_DEPTH_CAP = 8

# Bands. `unknown` counterparties are capped at "low" no matter what they wrote —
# anyone can type "enterprise rollout" into a cold DM.
VALUE_BANDS = (("critical", 75.0), ("high", 42.0), ("medium", 20.0), ("low", 8.0))
UNKNOWN_BAND_CAP = "low"


@dataclass
class Value:
    """What one counterparty is worth to us, and how confident that is."""
    score: float = 0.0
    band: str = "noise"                       # critical|high|medium|low|noise
    facts: List[str] = field(default_factory=list)      # verifiable
    signals: List[str] = field(default_factory=list)    # inferred
    unknown: bool = False                     # we cannot say who this is
    needs_identification: bool = False        # unknown, but the signal is strong
    identified_by: str = ""                   # what pinned them down

    @property
    def rank(self) -> int:
        order = ["critical", "high", "medium", "low", "noise"]
        return order.index(self.band) if self.band in order else len(order)

    def line(self) -> str:
        who = self.identified_by or ("unidentified" if self.unknown else "no CRM record")
        tail = " — WORTH IDENTIFYING" if self.needs_identification else ""
        return f"{self.band} ({int(self.score)}) — {who}{tail}"


def _revenue_points(amount: float) -> float:
    """Log-scaled: the difference between 0 and 50k matters; 2M and 4M does not."""
    if amount <= 0:
        return 0.0
    return min(VALUE_FACT_WEIGHTS["won_revenue"], 10.0 * math.log10(1.0 + amount / 1000.0))


def _band_for(score: float, unknown: bool) -> str:
    band = "noise"
    for name, floor in VALUE_BANDS:
        if score >= floor:
            band = name
            break
    if unknown:
        order = ["critical", "high", "medium", "low", "noise"]
        if order.index(band) < order.index(UNKNOWN_BAND_CAP):
            band = UNKNOWN_BAND_CAP
    return band


def value_of(
    *,
    name: str = "",
    headline: str = "",
    company: str = "",
    text: str = "",
    crm_tier: str = "",
    open_deal: bool = False,
    won_revenue: float = 0.0,
    prior_contact: bool = False,
    mutual_connections: Optional[int] = None,
    ever_replied: bool = False,
    outbound_count: int = 0,
    message_count: int = 0,
    cfg: Optional[Config] = None,
) -> Value:
    """Score one counterparty. Facts first, inference second, unknown declared."""
    r = _load_rubric(cfg, "linkedin")
    t1 = r.get("tier1", {})
    hay = _hay(headline, company, text, name)
    v = Value()

    # --- facts -------------------------------------------------------------
    if open_deal:
        v.score += VALUE_FACT_WEIGHTS["open_deal"]
        v.facts.append("open deal in the CRM")
    if won_revenue > 0:
        pts = _revenue_points(won_revenue)
        v.score += pts
        v.facts.append(f"closed-won ${won_revenue:,.0f}")
    if crm_tier:
        mapped = {k.lower(): val for k, val in (r.get("crm_tier_map") or {}).items()}.get(crm_tier.lower())
        v.score += VALUE_FACT_WEIGHTS["crm_tier_1"] if mapped == "tier-1" \
            else VALUE_FACT_WEIGHTS["crm_tier_other"]
        v.facts.append(f"CRM tier '{crm_tier}'")
    if prior_contact:
        v.score += VALUE_FACT_WEIGHTS["prior_contact"]
        v.facts.append("known contact with a real touch")

    # --- our own behaviour is a signal we generated, so it sits between -----
    if ever_replied:
        v.score += VALUE_SIGNAL_WEIGHTS["replied_before"]
        v.signals.append("we have replied before")
    if outbound_count:
        v.score += VALUE_SIGNAL_WEIGHTS["reply_depth"] * min(outbound_count, REPLY_DEPTH_CAP)
    if message_count:
        v.score += VALUE_SIGNAL_WEIGHTS["thread_depth"] * min(message_count, THREAD_DEPTH_CAP)

    # --- inference ---------------------------------------------------------
    for key, listname, label in (
        ("archetype", "buyer_archetypes", "buyer archetype"),
        ("vertical", "verticals", "vertical"),
        ("platform_buyer", "platform_buyers", "platform/API"),
        ("major_company", "companies", "major company"),
        ("provider", "providers", "provider"),
        ("intent", "intent_keywords", "buying intent"),
    ):
        hits = _all_in(hay, t1.get(listname, []))
        if hits:
            v.score += VALUE_SIGNAL_WEIGHTS[key] * len(hits)
            v.signals.append(f"{label}: {', '.join(hits[:2])}")
    senior = _any_in(hay, t1.get("seniority_keywords", []))
    if senior:
        v.score += VALUE_SIGNAL_WEIGHTS["seniority"]
        v.signals.append(f"decision-maker title: '{senior}'")
    floor = t1.get("min_mutual_connections_signal", 5)
    if mutual_connections is not None and mutual_connections >= floor:
        v.score += VALUE_SIGNAL_WEIGHTS["mutuals"]
        v.signals.append(f"{mutual_connections} mutual connections")

    # --- can we actually say who this is? ----------------------------------
    # A name alone is not an identity. Without a company, a title, a CRM record,
    # or a conversation we participated in, we do not know this person — and an
    # unknown must never be able to make anything downstream look important.
    if v.facts:
        v.identified_by = v.facts[0]
    elif company:
        v.identified_by = f"company '{company}'"
    elif senior:
        v.identified_by = f"title '{senior}'"
    elif ever_replied:
        v.identified_by = "a conversation we took part in"
    v.unknown = not bool(v.identified_by)

    # A cold message with real buying signal from someone we cannot attribute to
    # an organization is not low value — it is UNIDENTIFIED value, and the next
    # action is identification, not a reply written in the dark. Capping it to
    # "low" silently and moving on is how a real lead gets buried.
    raw_band = _band_for(v.score, unknown=False)
    v.band = _band_for(v.score, v.unknown)
    stated_intent = any(sig.startswith("buying intent") for sig in v.signals)
    if v.unknown and (raw_band in ("critical", "high") or stated_intent):
        v.needs_identification = True
        v.signals.append(
            f"asked something commercial but we cannot attribute them — "
            f"would rank {raw_band} once identified")
    return v


# --------------------------------------------------------------------------- #
# Commitments — what WE promised and never delivered
# --------------------------------------------------------------------------- #
#
# Structurally invisible to ordinary triage: these live in threads we already
# replied to, so "owed" is false and they sort as nothing-to-do. They are also
# the most expensive thing in an executive's inbox, because the other side is
# still waiting on a specific named person.
#
# Not every promise is worth chasing. "I'll intro you to someone" to a
# counterparty we cannot even identify is noise, and listing it next to an
# unsent contract is what makes a report unreadable.

# What kind of promise, and how much it costs to break. Anything touching money
# or a signature outranks a courtesy.
COMMITMENT_TYPES: Tuple[Tuple[str, float, Tuple[str, ...]], ...] = (
    ("legal_payment", 1.6, ("contract", "msa", "nda", "invoice", "purchase order",
                            "po ", "sign", "signature", "terms", "agreement",
                            "payment", "refund", "credit")),
    ("pricing", 1.4, ("pricing", "price", "quote", "rate card", "numbers",
                      "estimate", "proposal", "commercials", "discount")),
    ("decision", 1.3, ("get back to you", "come back to you", "let you know",
                       "check with", "check internally", "confirm", "revert",
                       "decide", "look into", "look at it", "review it")),
    ("schedule", 1.2, ("set up", "schedule", "book", "find time", "calendar",
                       "invite", "call next", "meet next", "jump on a call")),
    ("materials", 1.1, ("send", "share", "forward", "deck", "doc", "document",
                        "case study", "one-pager", "link", "access", "demo",
                        "trial", "sample", "spec", "brief")),
    ("intro", 0.9, ("intro", "introduce", "connect you", "put you in touch",
                    "loop in", "loop him", "loop her", "loop them")),
)

# First person, forward-looking. Deliberately narrow: "let me know" is asking
# THEM for something and must never read as a promise.
_PROMISE_RE = re.compile(
    r"(?i)\b("
    r"i'?ll|i will|we'?ll|we will|i'?m going to|we'?re going to|"
    r"let me|i can|i could|happy to|glad to|i'?d be happy to|"
    r"i'?ll go ahead and|will get|will send|will share|will check|will revert"
    r")\b(?P<rest>[^.!?\n]{0,120})")

# Asking, not promising. These swallow the same verbs and must be excluded.
_NOT_A_PROMISE_RE = re.compile(
    r"(?i)\b(let me know|let us know|can you|could you|would you|do you|"
    r"if you can|feel free|no rush|whenever you|up to you|let me know if)\b")

# Words that mean the thing actually went out.
_DELIVERED_RE = re.compile(
    r"(?i)\b(attached|attaching|here'?s|here is|sent|sending|shared|sharing|"
    r"enclosed|please find|as promised|as discussed, here|link below|"
    r"just sent|have sent|following up with the|booked|scheduled|"
    r"calendar invite|invite sent|signed|countersigned)\b")

# Them chasing us. The single strongest evidence a promise still matters.
_CHASE_RE = re.compile(
    r"(?i)\b(any update|any news|following up|checking in|circling back|"
    r"did you get a chance|still waiting|gentle (re)?minder|bump|"
    r"have you had a chance|when do you think|any luck|wondering if)\b")

# A promise whose object we cannot resolve. "I'll intro you to someone" is not a
# commitment anyone can act on, and a report full of them teaches people to
# ignore the report.
_VAGUE_TARGET_RE = re.compile(
    r"(?i)\b(someone|somebody|some ?one|a few (?:people|folks)|people|folks|"
    r"others|anyone|the right person|the team|a couple of people)\b")


def _names_a_subject(obj: str) -> bool:
    """Does this promise name WHO or WHAT, specifically?

    An intro is only actionable if a human could carry it out without asking a
    follow-up question. "I'll intro you to Dana at Kestrel" is a task; "I'll
    intro you to someone who can help" is a pleasantry, and a report full of
    pleasantries is what teaches people to stop reading the report.
    """
    if re.search(r"\bat\s+[A-Z][\w&.\-]+", obj):
        return True
    # A capitalized token that is not simply the first word.
    for token in obj.split()[1:]:
        clean = token.strip(".,;:!?()\"'")
        if len(clean) > 1 and clean[0].isupper() and not clean.isupper():
            return True
    return False

STALE_DAYS = 180          # beyond this, only a real relationship keeps it alive
COMMITMENT_FLOOR = 12.0   # below this it is chatter, not a commitment


@dataclass
class Commitment:
    """One promise we made, with everything needed to judge whether it matters."""
    kind: str
    promised_at: Optional[date]
    quote: str
    obj: str = ""
    fulfilled: bool = False
    fulfilled_note: str = ""
    chased: bool = False
    days_overdue: int = 0
    value: float = 0.0
    band: str = "noise"
    drop_reason: str = ""     # why it is not worth surfacing, if so

    @property
    def actionable(self) -> bool:
        return not self.fulfilled and not self.drop_reason


def _classify(text: str) -> Tuple[str, float]:
    low = text.lower()
    for kind, weight, needles in COMMITMENT_TYPES:
        if any(n in low for n in needles):
            return kind, weight
    return "other", 0.8


def _object_of(rest: str) -> str:
    """The thing promised, roughly. Good enough to name it back to a human."""
    obj = re.sub(r"(?i)^\s*(go ahead and\s+)?(to\s+)?", "", rest).strip(" ,:;-—")
    obj = re.split(r"\b(?:so that|because|once|when|after|and i|and we)\b", obj)[0]
    return " ".join(obj.split())[:110]


def commitments(
    messages: Sequence[Any],
    *,
    today: date,
    value: Optional[Value] = None,
) -> List[Commitment]:
    """Find promises we made and never kept.

    `messages` is any sequence with `.direction`, `.body`, `.at` — the engine's
    LIMessage, or anything shaped like it.
    """
    out: List[Commitment] = []
    ordered = sorted(messages, key=lambda m: (getattr(m, "at", None) or date.min))
    band = value.band if value else "noise"

    for idx, msg in enumerate(ordered):
        if getattr(msg, "direction", "") != "outbound":
            continue
        body = getattr(msg, "body", "") or ""
        for sentence in re.split(r"(?<=[.!?\n])\s+", body):
            if _NOT_A_PROMISE_RE.search(sentence):
                continue
            m = _PROMISE_RE.search(sentence)
            if not m:
                continue
            rest = m.group("rest") or ""
            obj = _object_of(rest)
            if not obj:
                continue
            kind, weight = _classify(m.group(0))
            at = getattr(msg, "at", None)
            c = Commitment(kind=kind, promised_at=at, obj=obj,
                           quote=" ".join(sentence.split())[:200])

            later = ordered[idx + 1:]
            # Delivered if a later message of ours names the object again, or
            # simply reads like a delivery.
            head = " ".join(obj.split()[:4]).lower()
            for nxt in later:
                if getattr(nxt, "direction", "") != "outbound":
                    continue
                nb = (getattr(nxt, "body", "") or "")
                if _DELIVERED_RE.search(nb) or (head and head in nb.lower()):
                    c.fulfilled = True
                    c.fulfilled_note = " ".join(nb.split())[:120]
                    break
            c.chased = any(getattr(n, "direction", "") == "inbound"
                           and _CHASE_RE.search(getattr(n, "body", "") or "")
                           for n in later)
            c.days_overdue = max(0, (today - at).days) if at else 0

            # --- is it worth a person's attention? --------------------------
            base = (value.score if value else 0.0) * weight
            if c.chased:
                base *= 1.8                     # they are still waiting, out loud
            if c.days_overdue > 14:
                base *= 1.25                    # aging matters, but only somewhat
            c.value = round(base, 1)
            c.band = band

            if c.fulfilled:
                c.drop_reason = "already delivered"
            elif value and value.unknown and kind == "intro":
                # The example that motivates this whole gate: an intro we cannot
                # name a subject for, to a person we cannot identify, is noise.
                c.drop_reason = "intro with no identifiable counterparty"
            elif kind == "intro" and (_VAGUE_TARGET_RE.search(obj) or not _names_a_subject(obj)):
                c.drop_reason = "intro with no named subject"
            elif band == "noise":
                c.drop_reason = "counterparty is noise"
            elif c.days_overdue > STALE_DAYS and not c.chased and band in ("low", "medium"):
                c.drop_reason = f"stale ({c.days_overdue}d, never chased)"
            elif c.value < COMMITMENT_FLOOR:
                c.drop_reason = f"below the value floor ({c.value:.0f} < {COMMITMENT_FLOOR:.0f})"
            out.append(c)

    out.sort(key=lambda c: (not c.actionable, -c.value, -c.days_overdue))
    return out


# --------------------------------------------------------------------------- #
# Deadlines — what has a clock on it
# --------------------------------------------------------------------------- #
#
# Resolved against the DATE OF THE MESSAGE, never against today. "by Friday"
# written in June means a Friday in June; resolving it against the current week
# turns a four-month-old miss into something that looks fresh.

_WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
             "friday": 4, "saturday": 5, "sunday": 6}
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"])}
_MONTH_ABBR = {m[:3]: i + 1 for m, i in ((k, v - 1) for k, v in _MONTHS.items())}

_DEADLINE_CUES = (r"by", r"before", r"no later than", r"due", r"deadline is",
                  r"need(?:s|ed)? (?:it|this|them)? ?by", r"ahead of", r"prior to",
                  r"in time for", r"we launch", r"going live")


@dataclass
class Deadline:
    phrase: str
    due: Optional[date]
    stated_at: Optional[date]
    quote: str = ""
    value: float = 0.0

    def status(self, today: date) -> str:
        if self.due is None:
            return "unresolved"
        delta = (self.due - today).days
        if delta < 0:
            return f"passed {abs(delta)}d ago"
        if delta == 0:
            return "today"
        if delta <= 3:
            return f"in {delta}d"
        return f"in {delta}d"

    def overdue_days(self, today: date) -> int:
        return max(0, (today - self.due).days) if self.due else 0


def _resolve_date(phrase: str, anchor: date) -> Optional[date]:
    """Turn a stated deadline into a real date, relative to when it was written."""
    p = phrase.lower().strip()
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", p)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})\b", p)
    if m:
        month = _MONTH_ABBR.get(m.group(1)[:3])
        try:
            cand = date(anchor.year, month, int(m.group(2)))
            # A month already behind us means they meant next year.
            return cand if cand >= anchor - timedelta(days=180) else date(anchor.year + 1, month, int(m.group(2)))
        except (ValueError, TypeError):
            return None
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)\b", p)
    if m and "week" not in p and "month" not in p:
        day = int(m.group(1))
        try:
            cand = date(anchor.year, anchor.month, day)
            return cand if cand >= anchor else (
                date(anchor.year + (anchor.month == 12), (anchor.month % 12) + 1, day))
        except ValueError:
            return None
    if "eod" in p or "end of day" in p or "today" in p:
        return anchor
    if "tomorrow" in p:
        return anchor + timedelta(days=1)
    m = re.search(r"\bin (\d{1,2}) (day|week|month)s?\b", p)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        return anchor + timedelta(days=n * {"day": 1, "week": 7, "month": 30}[unit])
    if "end of the week" in p or "end of week" in p or "eow" in p:
        return anchor + timedelta(days=(4 - anchor.weekday()) % 7)
    if "end of the month" in p or "end of month" in p or "eom" in p:
        nxt = date(anchor.year + (anchor.month == 12), (anchor.month % 12) + 1, 1)
        return nxt - timedelta(days=1)
    if "next week" in p:
        return anchor + timedelta(days=7 - anchor.weekday() + 4)
    if "this week" in p:
        return anchor + timedelta(days=(4 - anchor.weekday()) % 7)
    for name, idx in _WEEKDAYS.items():
        if name in p:
            ahead = (idx - anchor.weekday()) % 7
            if "next" in p:
                ahead += 7
            elif ahead == 0:
                ahead = 7
            return anchor + timedelta(days=ahead)
    return None


def deadlines(messages: Sequence[Any], *, value: Optional[Value] = None) -> List[Deadline]:
    """Clocks the other side put on us. Inbound only — our own 'by Friday' is a
    commitment, not a deadline they imposed, and `commitments()` owns that."""
    cue = "|".join(_DEADLINE_CUES)
    pattern = re.compile(rf"(?i)\b(?:{cue})\b[^.!?\n]{{0,40}}")
    out: List[Deadline] = []
    for msg in messages:
        if getattr(msg, "direction", "") != "inbound":
            continue
        body = getattr(msg, "body", "") or ""
        anchor = getattr(msg, "at", None)
        for m in pattern.finditer(body):
            phrase = " ".join(re.split(r"[,;]", m.group(0))[0].split())
            due = _resolve_date(phrase, anchor) if anchor else None
            if due is None:
                continue
            sentence = body[max(0, m.start() - 60):m.end() + 60]
            d = Deadline(phrase=phrase, due=due, stated_at=anchor,
                         quote=" ".join(sentence.split())[:180])
            d.value = round((value.score if value else 0.0), 1)
            out.append(d)
    # Nearest first; a passed deadline sorts above a future one.
    out.sort(key=lambda d: (d.due or date.max))
    return out


# --------------------------------------------------------------------------- #
# Thread state — where a conversation actually stands
# --------------------------------------------------------------------------- #

_STAGE_CUES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("contracting", ("contract", "msa", "nda", "signature", "sign", "legal",
                     "procurement", "purchase order", "invoice")),
    ("negotiating", ("pricing", "discount", "quote", "terms", "budget",
                     "commercials", "rate", "per seat", "annual")),
    ("evaluating", ("trial", "pilot", "poc", "test", "demo", "sandbox",
                    "evaluate", "compare", "benchmark")),
    ("scheduling", ("call", "meeting", "calendar", "invite", "book",
                    "next week", "availability")),
    ("engaged", ("thanks", "sounds good", "interesting", "tell me more",
                 "how does", "what about", "question")),
)

_CLOSED_CUES = ("not a fit", "going with", "decided to", "no longer",
                "we'll pass", "not moving forward", "another vendor", "we signed")


@dataclass
class ThreadState:
    stage: str                  # cold | engaged | scheduling | evaluating | negotiating | contracting | closed
    owes: str                   # us | them | nobody
    quiet_days: int = 0
    blocking: str = ""
    summary: str = ""


def thread_state(messages: Sequence[Any], *, today: date,
                 open_commitments: Optional[Sequence[Commitment]] = None) -> ThreadState:
    """One line about where this stands — not the last line of the thread.

    The distinction that matters: a 14-message negotiation and a one-line cold
    pitch can have identical last messages.
    """
    ordered = sorted(messages, key=lambda m: (getattr(m, "at", None) or date.min))
    if not ordered:
        return ThreadState(stage="cold", owes="nobody", summary="no messages")
    text = " ".join((getattr(m, "body", "") or "") for m in ordered).lower()
    outbound = [m for m in ordered if getattr(m, "direction", "") == "outbound"]
    inbound = [m for m in ordered if getattr(m, "direction", "") == "inbound"]

    stage = "cold"
    if _any_in(f" {text} ", list(_CLOSED_CUES)):
        stage = "closed"
    elif not outbound:
        # We never replied. Whatever words they used, this is still cold — a
        # one-line pitch containing "question" is not an engaged conversation.
        stage = "cold"
    else:
        for name, cues in _STAGE_CUES:
            if any(c in text for c in cues):
                stage = name
                break
        if stage == "cold":
            stage = "engaged"

    last = ordered[-1]
    last_at = getattr(last, "at", None)
    quiet = (today - last_at).days if last_at else 0
    if stage == "closed":
        return ThreadState(stage="closed", owes="nobody", quiet_days=quiet,
                           blocking="", summary=f"closed, {len(ordered)} message(s), quiet {quiet}d")
    if getattr(last, "direction", "") == "inbound":
        owes = "us"
    elif open_commitments and any(c.actionable for c in open_commitments):
        owes = "us"          # we replied, but we promised something and never sent it
    elif outbound and not inbound[-1:]:
        owes = "them"
    else:
        owes = "them" if outbound else "nobody"

    blocking = ""
    if open_commitments:
        live = [c for c in open_commitments if c.actionable]
        if live:
            blocking = f"we owe: {live[0].obj}"
    if not blocking and owes == "us" and inbound:
        blocking = "unanswered: " + " ".join((inbound[-1].body or "").split())[:80]
    if not blocking and owes == "them":
        blocking = f"waiting on them ({quiet}d)"

    summary = (f"{stage}, {len(ordered)} message(s), "
               f"{'quiet ' + str(quiet) + 'd' if quiet else 'active'}, owes: {owes}")
    return ThreadState(stage=stage, owes=owes, quiet_days=quiet,
                       blocking=blocking, summary=summary)


# --------------------------------------------------------------------------- #
# Campaigns — one blast wearing many faces
# --------------------------------------------------------------------------- #
#
# Forty senders running the same sequence is ONE judgment, not forty. Scoring
# each in isolation both wastes the reader's attention and misses the strongest
# available signal: near-identical text from unrelated people is what a campaign
# IS, and no single message carries that evidence.

CAMPAIGN_MIN_MEMBERS = 3
# Empirical, not guessed. Across a sample of real inbound, genuine messages score
# 0.00 against each other on 3-word shingles, while spintax variants of one blast
# ("we help founders scale" / "we help CEOs scale") sit at 0.40-1.00. 0.45 caught
# every variant with zero genuine messages swept in; the margin is wide enough
# that the exact value is not load-bearing. Re-measure before moving it.
CAMPAIGN_SIMILARITY = 0.45

# Filler that is identical across everyone and would otherwise make unrelated
# messages look similar.
_STOP = {"the", "a", "an", "to", "of", "and", "or", "for", "in", "on", "at",
         "is", "are", "we", "i", "you", "your", "our", "it", "this", "that",
         "with", "be", "have", "has", "would", "could", "will", "if", "so",
         "hi", "hey", "hello", "thanks", "regards", "best"}


def _shingles(text: str, size: int = 3) -> set:
    words = [w for w in re.findall(r"[a-z']+", (text or "").lower()) if w not in _STOP]
    if len(words) < size:
        return set(words)
    return {" ".join(words[i:i + size]) for i in range(len(words) - size + 1)}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class Campaign:
    key: str
    members: List[str] = field(default_factory=list)   # identity keys
    sample: str = ""
    size: int = 0


def campaigns(items: Sequence[Tuple[str, str]],
              *, min_members: int = CAMPAIGN_MIN_MEMBERS,
              threshold: float = CAMPAIGN_SIMILARITY) -> List[Campaign]:
    """Cluster near-identical openers across DIFFERENT senders.

    `items` is (identity_key, opening_text). Single-link clustering over shingle
    similarity — O(n^2) on the spam bucket only, which is small enough, and
    dependency-free by design.
    """
    prepared = [(key, _shingles(text)) for key, text in items if text and text.strip()]
    clusters: List[List[int]] = []
    assigned: Dict[int, int] = {}
    for i, (_, shi) in enumerate(prepared):
        if not shi:
            continue
        for ci, cluster in enumerate(clusters):
            if any(_jaccard(shi, prepared[j][1]) >= threshold for j in cluster):
                cluster.append(i)
                assigned[i] = ci
                break
        else:
            assigned[i] = len(clusters)
            clusters.append([i])
    out: List[Campaign] = []
    for cluster in clusters:
        if len(cluster) < min_members:
            continue
        members = [prepared[i][0] for i in cluster]
        sample_key = members[0]
        sample = next((t for k, t in items if k == sample_key), "")
        out.append(Campaign(key=f"campaign:{sample_key}", members=members,
                            sample=" ".join(sample.split())[:160], size=len(members)))
    out.sort(key=lambda c: -c.size)
    return out


# --------------------------------------------------------------------------- #
# One human, one row — across invitations, DMs, and the CRM
# --------------------------------------------------------------------------- #

@dataclass
class Person:
    key: str
    name: str = ""
    url: str = ""
    surfaces: List[str] = field(default_factory=list)   # invitation | dm
    value: Optional[Value] = None
    note: str = ""

    @property
    def multi(self) -> bool:
        return len(set(self.surfaces)) > 1


def unify(invitations: Sequence[Any], conversations: Sequence[Any]) -> List[Person]:
    """Collapse the same human across surfaces.

    Someone who invited us AND messaged us is one person with two open threads,
    not two separate judgments in two separate reports — and answering the DM
    usually settles the invitation too.
    """
    people: Dict[str, Person] = {}

    def touch(key: str, name: str, url: str, surface: str) -> Person:
        p = people.get(key)
        if p is None:
            p = people[key] = Person(key=key, name=name, url=url)
        p.surfaces.append(surface)
        if not p.name and name:
            p.name = name
        if not p.url and url:
            p.url = url
        return p

    for inv in invitations:
        touch(getattr(inv, "key", "") or identity_key(getattr(inv, "public_url", ""), "",
                                                      getattr(inv, "name", "")),
              getattr(inv, "name", ""), getattr(inv, "public_url", ""), "invitation")
    for convo in conversations:
        key = identity_key(getattr(convo, "counterparty_url", ""), "",
                           getattr(convo, "counterparty", ""))
        touch(key, getattr(convo, "counterparty", ""),
              getattr(convo, "counterparty_url", ""), "dm")

    for p in people.values():
        if p.multi:
            p.note = ("also has a pending invitation — answering the message "
                      "usually settles both")
    return sorted(people.values(), key=lambda p: (not p.multi, p.name.lower()))


# --------------------------------------------------------------------------- #
# What changed since the last run
# --------------------------------------------------------------------------- #

@dataclass
class RunDiff:
    new: List[str] = field(default_factory=list)
    resolved: List[str] = field(default_factory=list)
    still_waiting: List[Tuple[str, int]] = field(default_factory=list)
    escalated: List[str] = field(default_factory=list)

    @property
    def quiet(self) -> bool:
        return not (self.new or self.resolved or self.escalated)


def diff_runs(previous: Dict[str, Any], current: Dict[str, Any]) -> RunDiff:
    """Compare two runs, keyed by identity.

    A report that looks identical every morning stops being read. `new` and
    `resolved` are what a person actually wants; "still waiting 20 days" is what
    turns a static list into pressure.
    """
    prev = previous.get("items", {}) if previous else {}
    cur = current.get("items", {})
    d = RunDiff()
    for key, item in cur.items():
        was = prev.get(key)
        if was is None:
            d.new.append(key)
            continue
        if item.get("bucket") != was.get("bucket"):
            order = ["escalation", "needs-reply", "hold", "fyi", "trash"]
            try:
                if order.index(item.get("bucket", "fyi")) < order.index(was.get("bucket", "fyi")):
                    d.escalated.append(key)
            except ValueError:
                pass
        waited = int(item.get("days_waiting") or 0)
        if waited and item.get("bucket") in ("escalation", "needs-reply"):
            d.still_waiting.append((key, waited))
    for key in prev:
        if key not in cur:
            d.resolved.append(key)
    d.still_waiting.sort(key=lambda kv: -kv[1])
    return d


# --------------------------------------------------------------------------- #
# Reply briefs — what a draft has to contain before anyone writes it
# --------------------------------------------------------------------------- #
#
# The engine does NOT write the prose. It has no model, and a template-generated
# reply in someone else's voice is worse than no reply — it is the exact thing
# that makes an inbox feel automated.
#
# What it does instead is assemble the brief: the one thing they asked, what we
# already promised, the clock, where the thread stands, and the specific facts a
# reply must contain. The model writes from that, in the CEO's voice, and the
# draft goes to 00-Drafts for approval like everything else.

DRAFT_BAR = (
    "One reason for writing, tied to their last message",
    "One relevant proof point, verifiable, matched to what they asked",
    "One low-friction CTA — a question or a 15-minute slot, not a contract-sized ask",
    "Every personalization claim source-backed (thread, CRM, or their site) or marked unknown",
    "No fake familiarity — tone matches the real depth of the relationship",
    "Grounded in the FULL thread, not the last message",
)


@dataclass
class ReplyBrief:
    counterparty: str
    value: Value
    state: ThreadState
    asked: str = ""                                   # their actual question
    owed_items: List[str] = field(default_factory=list)
    clock: str = ""
    must_include: List[str] = field(default_factory=list)
    do_not: List[str] = field(default_factory=list)
    thread_id: str = ""

    def to_markdown(self) -> str:
        lines = [f"### {self.counterparty}",
                 f"- value: {self.value.line()}",
                 f"- state: {self.state.summary}"]
        if self.state.blocking:
            lines.append(f"- blocking: {self.state.blocking}")
        if self.asked:
            lines.append(f'- they asked: "{self.asked}"')
        for item in self.owed_items:
            lines.append(f"- we promised: {item}")
        if self.clock:
            lines.append(f"- clock: {self.clock}")
        if self.must_include:
            lines.append("- the reply must contain:")
            lines += [f"    - {x}" for x in self.must_include]
        if self.do_not:
            lines.append("- do NOT:")
            lines += [f"    - {x}" for x in self.do_not]
        lines.append(f"- thread_id: {self.thread_id}")
        return "\n".join(lines)


_QUESTION_RE = re.compile(r"[^.!?\n]*\?")


def reply_brief(
    *,
    counterparty: str,
    messages: Sequence[Any],
    value: Value,
    state: ThreadState,
    open_commitments: Sequence[Commitment] = (),
    due: Sequence[Deadline] = (),
    today: date,
    thread_id: str = "",
) -> ReplyBrief:
    """Everything a good reply needs, so the draft is grounded rather than generic."""
    inbound = [m for m in messages if getattr(m, "direction", "") == "inbound"]
    last_in = sorted(inbound, key=lambda m: (getattr(m, "at", None) or date.min))[-1:] or [None]
    asked = ""
    if last_in[0] is not None:
        qs = _QUESTION_RE.findall(getattr(last_in[0], "body", "") or "")
        asked = " ".join((qs[-1] if qs else (getattr(last_in[0], "body", "") or "")).split())[:180]

    brief = ReplyBrief(counterparty=counterparty, value=value, state=state,
                       asked=asked, thread_id=thread_id)
    brief.owed_items = [f"{c.obj} (promised {c.days_overdue}d ago"
                        + (", they chased" if c.chased else "") + ")"
                        for c in open_commitments if c.actionable]
    live = [d for d in due if d.due]
    if live:
        nearest = live[0]
        brief.clock = f'"{nearest.phrase}" -> {nearest.due} ({nearest.status(today)})'

    # What the reply has to do, in order of what breaks trust if missed.
    if brief.owed_items:
        brief.must_include.append(
            "Deliver, or give a date. An apology without the thing is another broken promise.")
    if asked:
        brief.must_include.append("A direct answer to their question, first line.")
    if brief.clock:
        brief.must_include.append("Acknowledge the deadline explicitly, even if we missed it.")
    if value.facts:
        brief.must_include.append(f"Context we can verify: {'; '.join(value.facts[:2])}.")
    brief.must_include.append("One low-friction next step.")

    if value.unknown:
        brief.do_not.append(
            "Claim any relationship or detail — we cannot identify this person. "
            "Keep it short and ask who they are.")
    if not value.facts:
        brief.do_not.append("Reference revenue, deals, or history — there is no CRM record.")
    if state.stage in ("closed",):
        brief.do_not.append("Re-pitch. This thread was closed.")
    if state.quiet_days > 60:
        brief.do_not.append(
            f"Pretend the gap did not happen — it has been {state.quiet_days} days.")
    return brief
