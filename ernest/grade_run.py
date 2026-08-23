"""Run tier grading over real data and write sorted grade cards.

B2B: grade inbound mail threads (CRM tier > lists > inference).
Talent: grade sourcing rows (purpose=hire) against the ex-NovaLabs rubric.
Cards are remind/assign only — grading never sends or mutates anything.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from dataclasses import dataclass, field as dc_field
from typing import Dict, List, Optional, Tuple

from .config import Config, ensure_dirs
from . import li_insight
from .grading import (Grade, LinkedInDMGrade, LinkedInGrade, grade_b2b,
                      grade_linkedin_dm, grade_linkedin_inbound, grade_talent, pool_name)
from .sources import (Contact, Conversation, Invitation, Thread, load_contacts,
                      load_conversations, load_invitations, load_threads)

# Hiring/candidate threads are graded by the TALENT rubric, not as B2B sales leads —
# keep them out of the buyer pipeline so a candidate never reads as a customer.
_NON_B2B_RE = re.compile(r"(?i)(hire|hiring|candidate|applicant|recruit|resume|\bcv\b|\bintern|talent)")


def _crm_index(cfg: Config) -> Dict[str, Contact]:
    idx: Dict[str, Contact] = {}
    for c in load_contacts(cfg):
        if c.company:
            idx[c.company.lower()] = c
        if c.name:
            idx[c.name.lower()] = c
    return idx


def grade_threads(cfg: Config) -> List[Tuple[Thread, Grade]]:
    crm = _crm_index(cfg)
    out: List[Tuple[Thread, Grade]] = []
    for t in load_threads(cfg):
        if _NON_B2B_RE.search(" ".join(filter(None, [t.category, t.intent]))):
            continue  # a hire/candidate thread, not a sales lead
        match = crm.get(t.company.lower()) or crm.get((t.contact or "").lower())
        grade = grade_b2b(
            company=t.company,
            contact=t.contact,
            text=" ".join(filter(None, [t.subject, t.summary, t.status, t.intent])),
            category=t.category,
            crm_tier=match.tier if match else "",
            prior_contact=bool(match and match.last_touch),
            cfg=cfg,
        )
        out.append((t, grade))
    # Tier first, then strongest match (score), then who's waited longest.
    out.sort(key=lambda pair: (pair[1].rank, -pair[1].score, -(pair[0].days_waiting(cfg.today))))
    return out


def grade_sourcing(cfg: Config) -> List[Tuple[dict, Grade]]:
    path = cfg.data_dir / "sourcing" / "targets.csv"
    out: List[Tuple[dict, Grade]] = []
    if not path.is_file():
        return out
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if (row.get("purpose") or "").strip().lower() not in ("hire", "talent"):
                continue
            grade = grade_talent(
                name=row.get("name", ""),
                profile=row.get("profile", "") or row.get("note", ""),
                company=row.get("company", ""),
                title=row.get("title", ""),
                cfg=cfg,
            )
            out.append((row, grade))
    # Tier first, then strongest match (score), then name — so the best
    # candidates lead each tier instead of appearing in arbitrary CSV order.
    out.sort(key=lambda pair: (pair[1].rank, -pair[1].score, (pair[0].get("name") or "").lower()))
    return out


def _grade_lines(grade: Grade) -> List[str]:
    lines = [f"- tier: {grade.tier} (confidence: {grade.confidence}, match score: {int(grade.score)})"]
    if grade.reasons:
        lines.append(f"- why: {'; '.join(grade.reasons)}")
    if grade.flags:
        lines.append(f"- check: {'; '.join(grade.flags)}")
    return lines


def _b2b_card(cfg: Config, graded: List[Tuple[Thread, Grade]]) -> str:
    counts: Dict[str, int] = {}
    for _, g in graded:
        counts[g.tier] = counts.get(g.tier, 0) + 1
    summary = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    lines = [
        f"# B2B lead grades ({cfg.today.isoformat()})",
        "",
        "type: reminder-card",
        "source: local-export",
        f"items: {len(graded)} ({summary})",
        "",
        "Sorted Tier-1 first. Remind/assign only; say \"draft these\" for Tier-1 replies.",
        "",
    ]
    for n, (t, g) in enumerate(graded, 1):
        lines.append(f"## {n}. [{g.tier.upper()}] {t.contact or 'Unknown'} - {t.company or 'Unknown'}")
        lines += _grade_lines(g)
        if t.subject:
            lines.append(f"- subject: {t.subject}")
        lines.append(f"- thread_id: {t.id}")
        lines.append("")
    return "\n".join(lines)


def _talent_card(cfg: Config, graded: List[Tuple[dict, Grade]]) -> str:
    counts: Dict[str, int] = {}
    for _, g in graded:
        counts[g.tier] = counts.get(g.tier, 0) + 1
    summary = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    lines = [
        f"# Talent grades — {pool_name(cfg)} pool ({cfg.today.isoformat()})",
        "",
        "type: reminder-card",
        "source: local-export",
        f"items: {len(graded)} ({summary})",
        "",
        "Sorted Tier-1 first. Assign outreach owners; Tier-3 = skip.",
        "",
    ]
    for n, (row, g) in enumerate(graded, 1):
        lines.append(f"## {n}. [{g.tier.upper()}] {row.get('name', 'Candidate')}")
        lines += _grade_lines(g)
        if row.get("linkedin"):
            lines.append(f"- linkedin: {row['linkedin']}")
        lines.append("")
    return "\n".join(lines)


# How many invitations get their own section before the rest are bucketed.
# The ceiling is human, not technical: a review queue past ~15 items stops being
# read and becomes a second inbox. 6,780 pending invitations cannot be a list.
MAX_NAMED = 15

_LI_CSV_FIELDS = ["tier", "signal", "score", "confidence", "action", "name",
                  "public_url", "headline", "company", "location", "sent_at",
                  "days_waiting", "mutual_connections", "connections", "note",
                  "why", "check", "identity_key"]


def grade_invitations(cfg: Config) -> List[Tuple[Invitation, LinkedInGrade]]:
    """Grade every pending inbound invitation. Read-only; proposes, never acts."""
    crm = _crm_index(cfg)
    out: List[Tuple[Invitation, LinkedInGrade]] = []
    for inv in load_invitations(cfg):
        match = (crm.get((inv.company or "").lower())
                 or crm.get((inv.name or "").lower()))
        grade = grade_linkedin_inbound(
            name=inv.name,
            headline=inv.headline,
            note=inv.note,
            company=inv.company,
            location=inv.location,
            mutual_connections=inv.mutual_connections,
            connections=inv.connections,
            crm_tier=match.tier if match else "",
            prior_contact=bool(match and match.last_touch),
            cfg=cfg,
        )
        out.append((inv, grade))
    # Tier-1 first, then hold (press/investors/competitors, which rank just
    # below because they still need a person), then the strongest match, then
    # who has waited longest. LINKEDIN_RANK owns that order.
    out.sort(key=lambda pair: (pair[1].rank, -pair[1].score,
                               -(pair[0].days_waiting(cfg.today))))
    return out


@dataclass
class InvInsight:
    """Invitations have no thread, so no commitments and no state — but the same
    value question applies, and mass invite blasts are the dominant shape."""
    value: li_insight.Value


def analyze_invitations(cfg: Config) -> List[Tuple[Invitation, LinkedInGrade, InvInsight]]:
    crm = _crm_index(cfg)
    out: List[Tuple[Invitation, LinkedInGrade, InvInsight]] = []
    for inv, grade in grade_invitations(cfg):
        match = (crm.get((inv.company or "").lower()) or crm.get((inv.name or "").lower()))
        value = li_insight.value_of(
            name=inv.name, headline=inv.headline, company=inv.company or (match.company if match else ""),
            text=inv.note, crm_tier=match.tier if match else "",
            open_deal=bool(match and match.open_deal),
            won_revenue=float(match.won_revenue) if match else 0.0,
            prior_contact=bool(match and match.last_touch),
            mutual_connections=inv.mutual_connections, cfg=cfg)
        out.append((inv, grade, InvInsight(value=value)))
    out.sort(key=lambda t: (t[1].rank, t[2].value.rank, -t[2].value.score,
                            -(t[0].days_waiting(cfg.today))))
    return out


def _inv_state_path(cfg: Config) -> Path:
    return cfg.logs_dir / "linkedin-invitations-state.json"


def _li_sidecar(cfg: Config, graded: List[Tuple[Invitation, LinkedInGrade]]) -> Path:
    """Full population as CSV. The card shows the decisions; this holds the rows."""
    path = cfg.watch_dir / f"linkedin-invitations--{cfg.today.isoformat()}.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=_LI_CSV_FIELDS)
        w.writeheader()
        for inv, g in graded:
            w.writerow({
                "tier": g.tier, "signal": g.signal, "score": int(g.score),
                "confidence": g.confidence, "action": g.action,
                "name": inv.name, "public_url": inv.public_url,
                "headline": inv.headline, "company": inv.company,
                "location": inv.location,
                "sent_at": inv.sent_at.isoformat() if inv.sent_at else "",
                "days_waiting": inv.days_waiting(cfg.today) if inv.sent_at else "",
                "mutual_connections": "" if inv.mutual_connections is None else inv.mutual_connections,
                "connections": "" if inv.connections is None else inv.connections,
                "note": inv.note, "why": "; ".join(g.reasons),
                "check": "; ".join(g.flags), "identity_key": inv.key,
            })
    return path


_BUCKET_COPY = {
    "tier-2": ("Worth a look", "ICP-adjacent or unknown, no decisive buyer signal.",
               "Review the top rows in {csv} — ranked by score."),
    "trash": ("Spam / seller pitch", "Cold vendor, mass-template, or thin-network invites.",
              'Say "remove the spam" to queue Ignore in batches. Nothing happens until you do.'),
}


def _linkedin_card(cfg: Config, analyzed, csv_path: Path,
                   prev: Dict[str, object], dm_keys: Optional[set] = None) -> str:
    """The invitation report.

    Same shape as the DM report and for the same reason: named where a person
    has to decide, counted everywhere else. Invitations have no thread, so there
    are no commitments or deadlines here — but the value question and the
    mass-blast question both apply, and a 6,000-row queue is mostly blasts.
    """
    counts: Dict[str, int] = {}
    for _, g, _i in analyzed:
        counts[g.tier] = counts.get(g.tier, 0) + 1
    source = analyzed[0][0].source if analyzed else "local-export"
    dm_keys = dm_keys or set()

    named = [t for t in analyzed if t[1].tier in ("hold", "tier-1")][:MAX_NAMED]
    named_keys = {inv.key for inv, _, _ in named}
    overflow: Dict[str, int] = {}
    for inv, g, _i in analyzed:
        if inv.key not in named_keys:
            overflow[g.tier] = overflow.get(g.tier, 0) + 1

    identify = [t for t in analyzed
                if t[2].value.needs_identification and t[1].tier != "trash"][:MAX_NAMED]
    # Cluster on the NOTE, not the headline. A campaign varies its personas'
    # headlines on purpose ("Dedicated Developers" / "Offshore Team"); the
    # templated part is the message, and mixing the two dilutes the signal
    # below threshold exactly when it matters.
    camps = li_insight.campaigns(
        [(inv.key, inv.note or inv.headline) for inv, g, _ in analyzed if g.tier == "trash"])
    camp_members = {m for c in camps for m in c.members}
    both = [t for t in analyzed if t[0].key in dm_keys and t[1].tier != "trash"]

    diff = li_insight.diff_runs(prev, {"items": {inv.key: {
        "bucket": g.tier, "days_waiting": inv.days_waiting(cfg.today)}
        for inv, g, _ in analyzed}})

    lines = [
        f"# Watch: linkedin-invitations ({cfg.today.isoformat()})",
        "",
        "type: reminder-card",
        f"source: {source}",
        f"items: {len(analyzed)} pending — " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())),
        "",
        "Report only. Nothing is accepted, ignored, or reported until you say so.",
        f"Full population: {csv_path.name}",
        "",
    ]
    banner = _sample_data_banner([inv.public_url or inv.name for inv, _, _ in analyzed])
    if banner:
        lines += [banner, ""]
    if prev:
        bits = []
        if diff.new:
            bits.append(f"{len(diff.new)} new")
        if diff.resolved:
            bits.append(f"{len(diff.resolved)} cleared")
        lines.append(f"Since the last run: {', '.join(bits) if bits else 'nothing changed'}.")
        lines.append("")

    n = 0
    for inv, g, ins in named:
        n += 1
        who = inv.name or "Unknown"
        if inv.company:
            who += f" - {inv.company}"
        lines.append(f"## {n}. [{g.tier.upper()}] {who}")
        lines.append(f"- value: {ins.value.line()}")
        lines.append(f"- signal: {g.signal}")
        lines.append("- channel: Connection Request")
        if inv.public_url:
            lines.append(f"- linkedin: {inv.public_url}")
        if inv.sent_at:
            lines.append(f"- waiting: {inv.days_waiting(cfg.today)}d")
        if inv.note:
            note = inv.note if len(inv.note) <= 160 else inv.note[:157] + "..."
            lines.append(f'- note: "{note}"')
        if inv.key in dm_keys:
            lines.append("- also: has an open DM thread — answering that settles this too")
        lines.append(f"- why: {'; '.join(g.reasons) or 'No decisive signal'}")
        lines.append(f"- action: {g.action}")
        if g.flags:
            lines.append(f"- check: {'; '.join(g.flags)}")
        if g.tier == "tier-1" and g.action == "Accept":
            lines.append("- crm: PROPOSE linkedin_inbound_invitation_status=Accepted")
        lines.append("")

    if identify:
        n += 1
        lines.append(f"## {n}. [IDENTIFY] Strong signal, no idea who they are ({len(identify)})")
        lines.append("These wrote something commercial but cannot be attributed to a company.")
        lines.append("The next step is a 30-second lookup, not a reply in the dark.")
        for inv, g, ins in identify:
            lines.append(f"- {inv.name or 'Unknown'} — {ins.value.line()}")
            if inv.note:
                lines.append(f'    "{" ".join(inv.note.split())[:140]}"')
        lines.append("")

    if both:
        n += 1
        lines.append(f"## {n}. [BOTH SURFACES] Also in your DMs ({len(both)})")
        lines.append("One person, two open threads. Answer the message and this resolves itself.")
        for inv, g, ins in both[:MAX_NAMED]:
            lines.append(f"- {inv.name or 'Unknown'} — {ins.value.band}")
        lines.append("")

    for camp in camps:
        n += 1
        lines.append(f"## {n}. [CAMPAIGN] {camp.size} invites from one sequence")
        lines.append("One judgment, not " + str(camp.size) + ".")
        lines.append(f'- sample: "{camp.sample}"')
        lines.append("- action: ignore the whole cluster, or none of it")
        lines.append("")

    for tier in ("hold", "tier-1", "tier-2", "trash"):
        count = overflow.get(tier, 0)
        if tier == "trash":
            count -= len(camp_members)
        if count <= 0:
            continue
        n += 1
        title, why, action = _BUCKET_COPY.get(
            tier, (f"{tier} — not shown individually", "Above the on-card display limit.",
                   "Read the rows in {csv}."))
        if tier in ("hold", "tier-1"):
            title = f"{tier.upper()} above the display limit"
            why = f"{count} more scored {tier}; only the top {MAX_NAMED} are named."
            action = "Read the top rows in {csv} — these still need a person."
        lines.append(f"## {n}. [BUCKET] {title} ({count})")
        lines.append(f"- count: {count}")
        if tier == "trash":
            lines.append("- signal: Spam")
        lines.append(f"- why: {why}")
        lines.append(f"- action: {action.format(csv=csv_path.name)}")
        lines.append("")

    lines.append("Reply draft these when you want me to prepare actions.")
    lines.append("")
    return "\n".join(lines)


_DM_CSV_FIELDS = ["bucket", "signal", "score", "confidence", "action", "counterparty",
                  "public_url", "subject", "owed", "days_waiting", "messages",
                  "ever_replied", "folder", "last_message", "why", "check", "conversation_id"]

_DM_BUCKET_COPY = {
    "needs-reply": ("Waiting on you", "They wrote last and never got an answer.",
                    "Reply, or say \"draft these\" and I'll prepare them."),
    "hold": ("Hold for a person", "Press, investors, competitors, or legal.",
             "These never auto-resolve. Read them in {csv}."),
    "fyi": ("No action needed", "Nothing owed, or already handled.",
            "Skim {csv} if you want; nothing here is waiting on you."),
    "trash": ("Spam / cold pitches", "Cold sequences and vendor blasts you never answered.",
              'Say "clean up my LinkedIn DMs" to queue Archive in batches. Nothing happens until you do.'),
}


@dataclass
class DMInsight:
    """Everything worth knowing about one thread beyond its bucket."""
    value: li_insight.Value
    state: li_insight.ThreadState
    commitments: List[li_insight.Commitment] = dc_field(default_factory=list)
    deadlines: List[li_insight.Deadline] = dc_field(default_factory=list)

    @property
    def open_commitments(self) -> List[li_insight.Commitment]:
        return [c for c in self.commitments if c.actionable]

    @property
    def live_deadlines(self) -> List[li_insight.Deadline]:
        return [d for d in self.deadlines if d.due]


def grade_conversations(cfg: Config) -> List[Tuple[Conversation, LinkedInDMGrade]]:
    """Triage the DM inbox. Read-only; proposes an action, never takes one."""
    crm = _crm_index(cfg)
    out: List[Tuple[Conversation, LinkedInDMGrade]] = []
    for convo in load_conversations(cfg):
        match = crm.get((convo.counterparty or "").lower())
        grade = grade_linkedin_dm(
            counterparty=convo.counterparty, text=convo.text, opener=convo.opener,
            subject=convo.subject, folder=convo.folder, owed=convo.owed,
            ever_replied=convo.ever_replied,
            days_waiting=convo.days_waiting(cfg.today),
            message_count=len(convo.messages),
            crm_tier=match.tier if match else "",
            prior_contact=bool(match and match.last_touch), cfg=cfg)
        out.append((convo, grade))
    out.sort(key=lambda pair: (pair[1].rank, -(pair[0].days_waiting(cfg.today)),
                               -pair[1].score))
    return out


def analyze_conversations(cfg: Config) -> List[Tuple[Conversation, LinkedInDMGrade, DMInsight]]:
    """Grade every thread AND work out what is buried in it."""
    crm = _crm_index(cfg)
    out: List[Tuple[Conversation, LinkedInDMGrade, DMInsight]] = []
    for convo, grade in grade_conversations(cfg):
        match = crm.get((convo.counterparty or "").lower())
        value = li_insight.value_of(
            name=convo.counterparty, company=match.company if match else "",
            text=convo.text, crm_tier=match.tier if match else "",
            open_deal=bool(match and match.open_deal),
            won_revenue=float(match.won_revenue) if match else 0.0,
            prior_contact=bool(match and match.last_touch),
            ever_replied=convo.ever_replied,
            outbound_count=len([m for m in convo.messages if m.direction == "outbound"]),
            message_count=len(convo.messages), cfg=cfg)
        cms = li_insight.commitments(convo.messages, today=cfg.today, value=value)
        dls = li_insight.deadlines(convo.messages, value=value)
        state = li_insight.thread_state(convo.messages, today=cfg.today, open_commitments=cms)
        out.append((convo, grade, DMInsight(value=value, state=state,
                                            commitments=cms, deadlines=dls)))
    out.sort(key=lambda t: (t[1].rank, t[2].value.rank, -t[2].value.score))
    return out


def _dm_sidecar(cfg: Config, graded: List[Tuple[Conversation, LinkedInDMGrade]]) -> Path:
    path = cfg.watch_dir / f"linkedin-dms--{cfg.today.isoformat()}.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=_DM_CSV_FIELDS)
        w.writeheader()
        for convo, g in graded:
            last = sorted(convo.inbound, key=lambda m: (m.at or cfg.today))[-1].body if convo.inbound else ""
            w.writerow({
                "bucket": g.bucket, "signal": g.signal, "score": int(g.score),
                "confidence": g.confidence, "action": g.action,
                "counterparty": convo.counterparty, "public_url": convo.counterparty_url,
                "subject": convo.subject, "owed": "yes" if convo.owed else "no",
                "days_waiting": convo.days_waiting(cfg.today) if convo.last_inbound else "",
                "messages": len(convo.messages),
                "ever_replied": "yes" if convo.ever_replied else "no",
                "folder": convo.folder, "last_message": last[:400],
                "why": "; ".join(g.reasons), "check": "; ".join(g.flags),
                "conversation_id": convo.id,
            })
    return path


def _sample_data_banner(rows: List[str]) -> Optional[str]:
    """Say plainly when a report is built on the shipped sample rows.

    Otherwise the only tell is that the names end in "-sample", which a reader
    has to notice for themselves — and a convincing report about fictional
    people is worse than no report.
    """
    if not rows:
        return None
    fake = sum(1 for r in rows if "-sample" in (r or "").lower())
    if fake and fake >= len(rows) * 0.5:
        return ("> **This is SAMPLE data — these people are not real.** "
                f"{fake} of {len(rows)} rows are the shipped fixtures. "
                "Import a real export to replace them: LinkedIn -> Settings -> "
                "Data Privacy -> Get a copy of your data -> tick Invitations and "
                "Messages, then run the ingest with --from-archive <the zip>.")
    return None


def _dm_state_path(cfg: Config) -> Path:
    return cfg.logs_dir / "linkedin-dms-state.json"


def _load_state(path: Path) -> Dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_prev_state(cfg: Config) -> Dict[str, object]:
    return _load_state(_dm_state_path(cfg))


def _save_state(cfg: Config, analyzed) -> Dict[str, object]:
    state = {"date": cfg.today.isoformat(),
             "items": {c.id: {"bucket": g.bucket,
                              "days_waiting": c.days_waiting(cfg.today),
                              "value": ins.value.band}
                       for c, g, ins in analyzed}}
    path = _dm_state_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state


def _linkedin_dm_card(cfg: Config, analyzed, csv_path: Path, prev: Dict[str, object]) -> str:
    """The DM report.

    Ordered by what costs most to get wrong, not by what is easiest to compute:
    escalations, then promises WE broke, then clocks that have run out, then who
    is waiting. Spam is a number at the bottom — it is the least of it.
    """
    counts: Dict[str, int] = {}
    for _, g, _ins in analyzed:
        counts[g.bucket] = counts.get(g.bucket, 0) + 1
    source = analyzed[0][0].source if analyzed else "local-export"

    escalations = [(c, g, i) for c, g, i in analyzed if g.bucket == "escalation"]
    owed_us = sorted(
        [(c, g, i) for c, g, i in analyzed if i.open_commitments and g.bucket != "trash"],
        key=lambda t: -max(x.value for x in t[2].open_commitments))
    clocks = sorted(
        [(c, g, i, d) for c, g, i in analyzed if g.bucket != "trash"
         for d in i.live_deadlines],
        key=lambda t: (t[3].due, -t[2].value.score))
    waiting = [(c, g, i) for c, g, i in analyzed
               if g.bucket == "needs-reply" and not i.open_commitments]
    holds = [(c, g, i) for c, g, i in analyzed if g.bucket == "hold"]

    # One blast wearing many faces is one judgment, not N.
    camps = li_insight.campaigns([(c.id, c.opener) for c, g, _ in analyzed if g.bucket == "trash"])
    camp_members = {m for camp in camps for m in camp.members}

    diff = li_insight.diff_runs(prev, {"items": {c.id: {"bucket": g.bucket,
                                                        "days_waiting": c.days_waiting(cfg.today)}
                                                 for c, g, _ in analyzed}})

    lines = [
        f"# Watch: linkedin-dms ({cfg.today.isoformat()})",
        "",
        "type: reminder-card",
        f"source: {source}",
        f"items: {len(analyzed)} thread(s) — " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())),
        "",
        "Report only. Nothing is replied to, archived, or reported until you say so.",
        f"Full population: {csv_path.name}",
        "",
    ]
    banner = _sample_data_banner([c.counterparty_url or c.counterparty for c, _, _ in analyzed])
    if banner:
        lines += [banner, ""]
    if prev:
        bits = []
        if diff.new:
            bits.append(f"{len(diff.new)} new")
        if diff.escalated:
            bits.append(f"{len(diff.escalated)} got more urgent")
        if diff.resolved:
            bits.append(f"{len(diff.resolved)} cleared")
        lines.append(f"Since the last run: {', '.join(bits) if bits else 'nothing changed'}.")
        lines.append("")

    n = 0

    def head(title: str, note: str = "") -> None:
        nonlocal n
        n += 1
        lines.append(f"## {n}. {title}")
        if note:
            lines.append(note)

    def person(convo, ins) -> str:
        who = convo.counterparty or "Unknown"
        return f"{who} — {ins.value.line()}"

    for convo, g, ins in escalations[:MAX_NAMED]:
        head(f"[ESCALATION] {person(convo, ins)}")
        lines.append(f"- why: {'; '.join(g.reasons)}")
        lines.append(f"- state: {ins.state.summary}")
        last = sorted(convo.inbound, key=lambda m: (m.at or cfg.today))[-1].body if convo.inbound else ""
        if last:
            lines.append(f'- said: "{" ".join(last.split())[:180]}"')
        lines.append(f"- action: {g.action}")
        lines.append(f"- thread_id: {convo.id}")
        lines.append("")

    if owed_us:
        head("[YOU PROMISED] Unkept commitments",
             "Sorted by what it costs to keep breaking them. "
             "Delivered, vague, and no-name promises are filtered out.")
        for convo, g, ins in owed_us[:MAX_NAMED]:
            for c in ins.open_commitments[:2]:
                lines.append(f"- {convo.counterparty or 'Unknown'} — {ins.value.band} — "
                             f"{c.kind}, {c.days_overdue}d ago"
                             + (", **they chased**" if c.chased else ""))
                lines.append(f'    "{c.quote}"')
        lines.append("")

    if clocks:
        head("[CLOCK] Deadlines they set",
             "Resolved against the date the message was written, not today.")
        for convo, g, ins, d in clocks[:MAX_NAMED]:
            lines.append(f"- {convo.counterparty or 'Unknown'} — {ins.value.band} — "
                         f'"{d.phrase}" -> {d.due} ({d.status(cfg.today)})')
        lines.append("")

    if waiting:
        head("[WAITING] They wrote last and got no answer")
        for convo, g, ins in waiting[:MAX_NAMED]:
            lines.append(f"- {person(convo, ins)} — {convo.days_waiting(cfg.today)}d — "
                         f"{ins.state.stage}")
            last = sorted(convo.inbound, key=lambda m: (m.at or cfg.today))[-1].body if convo.inbound else ""
            if last:
                lines.append(f'    "{" ".join(last.split())[:150]}"')
        lines.append("")

    for convo, g, ins in holds[:MAX_NAMED]:
        head(f"[HOLD] {convo.counterparty or 'Unknown'}")
        lines.append(f"- why: {'; '.join(g.reasons)}")
        lines.append(f"- action: {g.action}")
        lines.append(f"- thread_id: {convo.id}")
        lines.append("")

    for camp in camps:
        head(f"[CAMPAIGN] {camp.size} senders running the same sequence",
             "One judgment, not " + str(camp.size) + ".")
        lines.append(f'- sample: "{camp.sample}"')
        lines.append(f"- action: archive the whole cluster, or none of it")
        lines.append("")

    solo_spam = counts.get("trash", 0) - len(camp_members)
    if solo_spam > 0:
        head(f"[BUCKET] Spam / cold pitches ({solo_spam})")
        lines.append("- signal: Spam")
        lines.append('- action: Say "clean up my LinkedIn DMs" to queue Archive in batches.')
        lines.append("")
    if counts.get("fyi"):
        head(f"[BUCKET] No action needed ({counts['fyi']})")
        lines.append(f"- action: Skim {csv_path.name} if you want; nothing here is waiting on you.")
        lines.append("")

    if diff.still_waiting:
        head("[AGING] Longest unanswered")
        by_id = {c.id: c for c, _, _ in analyzed}
        for key, days in diff.still_waiting[:5]:
            convo = by_id.get(key)
            if convo:
                lines.append(f"- {convo.counterparty or key} — {days}d and counting")
        lines.append("")

    lines.append("Reply draft these when you want me to prepare actions.")
    lines.append("")
    return "\n".join(lines)


def run(cfg: Config, *, b2b: bool = True, talent: bool = True,
        linkedin: bool = True, linkedin_dms: bool = True) -> List[Path]:
    ensure_dirs(cfg)
    written: List[Path] = []
    if b2b:
        graded = grade_threads(cfg)
        if graded:
            path = cfg.watch_dir / f"b2b-grades--{cfg.today.isoformat()}.md"
            path.write_text(_b2b_card(cfg, graded), encoding="utf-8")
            written.append(path)
    if talent:
        graded_t = grade_sourcing(cfg)
        if graded_t:
            path = cfg.watch_dir / f"talent-grades--{cfg.today.isoformat()}.md"
            path.write_text(_talent_card(cfg, graded_t), encoding="utf-8")
            written.append(path)
    if linkedin:
        analyzed_i = analyze_invitations(cfg)
        if analyzed_i:
            # The same human in both queues is one person, not two problems.
            dm_keys = {li_insight.identity_key(c.counterparty_url, "", c.counterparty)
                       for c in load_conversations(cfg)}
            prev_i = _load_state(_inv_state_path(cfg))
            sidecar = _li_sidecar(cfg, [(i, g) for i, g, _ in analyzed_i])
            path = cfg.watch_dir / f"linkedin-invitations--{cfg.today.isoformat()}.md"
            path.write_text(_linkedin_card(cfg, analyzed_i, sidecar, prev_i, dm_keys),
                            encoding="utf-8")
            _save_json(_inv_state_path(cfg), {"date": cfg.today.isoformat(), "items": {
                inv.key: {"bucket": g.tier, "days_waiting": inv.days_waiting(cfg.today)}
                for inv, g, _ in analyzed_i}})
            written += [path, sidecar]
    if linkedin_dms:
        analyzed = analyze_conversations(cfg)
        if analyzed:
            prev = _load_prev_state(cfg)
            sidecar = _dm_sidecar(cfg, [(c, g) for c, g, _ in analyzed])
            path = cfg.watch_dir / f"linkedin-dms--{cfg.today.isoformat()}.md"
            path.write_text(_linkedin_dm_card(cfg, analyzed, sidecar, prev), encoding="utf-8")
            _save_state(cfg, analyzed)
            written += [path, sidecar]
    return written
