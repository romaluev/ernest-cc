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
from .sources import (Contact, Conversation, Invitation, Thread, last_owner,
                      load_contacts, load_conversations, load_invitations,
                      load_threads)

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

# The card is the human view; this is the audit trail. `lane` and `summary` are
# what the card shows, `why` is every rubric list that matched — both live here
# so a disagreement can be traced without re-running the grader.
_LI_CSV_FIELDS = ["tier", "lane", "summary", "signal", "score", "confidence", "action", "name",
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
                "tier": g.tier, "lane": getattr(g, "lane", ""),
                "summary": getattr(g, "summary", ""),
                "signal": g.signal, "score": int(g.score),
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


# What a lane IS, in the words a person would use. The report says
# "2 investors, 1 competitor", never "2 tier-1, 1 hold" — a tier is our
# bookkeeping, a lane is the answer to "who is this".
_LANE_WORDS = {
    "investor": ("investor", "investors"),
    "customer": ("customer", "customers"),
    "enterprise": ("enterprise buyer", "enterprise buyers"),
    "influencer": ("creator", "creators"),
    "buyer": ("ICP buyer", "ICP buyers"),
    "colleague": ("colleague", "colleagues"),
    "talent": ("possible hire", "possible hires"),
    "partnership": ("partnership offer", "partnership offers"),
    "seller": ("seller", "sellers"),
    "consultant": ("consultant", "consultants"),
    "applicant": ("cold applicant", "cold applicants"),
    "press": ("journalist", "journalists"),
    "competitor": ("competitor", "competitors"),
    "legal": ("legal/regulatory", "legal/regulatory"),
    "exec-claim": ("claimed prior contact", "claim prior contact"),
    "suppressed": ("suppressed contact", "suppressed contacts"),
    "unknown": ("unidentified", "unidentified"),
    "other": ("other", "other"),
}


def _lane_phrase(grades) -> str:
    """"2 investors, 1 creator" — biggest group first, at most four groups."""
    tally: Dict[str, int] = {}
    for g in grades:
        lane = getattr(g, "lane", "other")
        tally[lane] = tally.get(lane, 0) + 1
    ranked = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))
    bits = []
    for lane, count in ranked[:4]:
        one, many = _LANE_WORDS.get(lane, (lane, lane))
        bits.append(f"{count} {one if count == 1 else many}")
    if len(ranked) > 4:
        bits.append(f"{sum(c for _, c in ranked[4:])} other")
    return ", ".join(bits)


def _person_block(idx: int, inv, g, cfg: Config, *, in_dms: bool) -> List[str]:
    """One invitation, in as few lines as carry the decision.

    Deliberately not a key/value dump. The earlier version printed `value:`,
    `signal:`, `checked:` and a semicolon-joined list of every rubric list that
    matched — accurate, unreadable, and the reason the PDF came back described
    as slop. What a person needs is who, why, how long, and what to do.
    """
    who = inv.name or "Unknown"
    if inv.company:
        who += f" — {inv.company}"
    elif inv.headline:
        who += f" — {inv.headline.split('|')[0].strip()[:50]}"
    out = [f"**{idx}. {who}**"]

    line = g.summary or (g.reasons[0] if g.reasons else "No decisive signal.")
    if inv.sent_at:
        line += f" Waiting {inv.days_waiting(cfg.today)}d."
    out.append(line)

    if inv.note:
        note = " ".join(inv.note.split())
        out.append(f'> "{note if len(note) <= 180 else note[:177] + "..."}"')

    do = g.action
    if in_dms:
        do += " (also has an open DM — answering that settles both)"
    if inv.public_url:
        do += f" · {inv.public_url}"
    out.append(f"Do: {do}")
    if g.flags and g.tier in ("hold", "tier-1"):
        out.append(f"Check: {g.flags[0]}")
    out.append("")
    return out


def _linkedin_card(cfg: Config, analyzed, csv_path: Path,
                   prev: Dict[str, object], dm_keys: Optional[set] = None) -> str:
    """The invitation report: a TL;DR, then the people, then the counts.

    Shape follows what the reader actually does with it — decide on a handful,
    approve a batch, ignore the rest. Tier-1 and hold are named individually
    (capped); everything else is a count and a pointer to the CSV, because a
    card that lists 6,780 people is a second inbox, not a report.
    """
    counts: Dict[str, int] = {}
    for _, g, _i in analyzed:
        counts[g.tier] = counts.get(g.tier, 0) + 1
    source = analyzed[0][0].source if analyzed else "local-export"
    dm_keys = dm_keys or set()

    accept = [t for t in analyzed if t[1].tier == "tier-1"]
    decide = [t for t in analyzed if t[1].tier == "hold"]
    ignore = [t for t in analyzed if t[1].tier == "trash"]
    rest = [t for t in analyzed if t[1].tier in ("tier-2", "unknown")]
    talent = [t for t in rest if getattr(t[1], "lane", "") == "talent"]

    identify = [t for t in analyzed
                if t[2].value.needs_identification and t[1].tier != "trash"][:MAX_NAMED]
    # Cluster on the NOTE, not the headline. A campaign varies its personas'
    # headlines on purpose ("Dedicated Developers" / "Offshore Team"); the
    # templated part is the message, and mixing the two dilutes the signal
    # below threshold exactly when it matters.
    camps = li_insight.campaigns(
        [(inv.key, inv.note or inv.headline) for inv, g, _ in analyzed if g.tier == "trash"])
    diff = li_insight.diff_runs(prev, {"items": {inv.key: {
        "bucket": g.tier, "days_waiting": inv.days_waiting(cfg.today)}
        for inv, g, _ in analyzed}})

    need = len(accept) + len(decide)
    lines = [
        f"# LinkedIn invitations — {cfg.today.strftime('%d %b %Y')}",
        "",
        "type: reminder-card",
        f"source: {source}",
        f"items: {len(analyzed)} pending — "
        + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())),
        "",
        "## TL;DR",
        "",
        f"- **{len(analyzed)} pending invitations. {need} need you.**",
    ]
    if accept:
        lines.append(f"- **Accept ({len(accept)})** — {_lane_phrase([g for _, g, _ in accept])}.")
    if decide:
        lines.append(f"- **Your call ({len(decide)})** — {_lane_phrase([g for _, g, _ in decide])}."
                     " These never resolve on their own.")
    if talent:
        lines.append(f"- **Talent lane ({len(talent)})** — applied, with a real background behind it.")
    if ignore:
        lines.append(f"- **Ignore ({len(ignore)})** — {_lane_phrase([g for _, g, _ in ignore])}."
                     ' Say "clean up the spam" and I will queue them in batches.')
    other = len(rest) - len(talent)
    if other > 0:
        lines.append(f"- **{other} unclear** — close to what we sell, nothing decisive. "
                     f"Ranked in {csv_path.name}; nothing owed today.")
    if prev:
        bits = []
        if diff.new:
            bits.append(f"{len(diff.new)} new")
        if diff.resolved:
            bits.append(f"{len(diff.resolved)} cleared")
        lines.append(f"- Since the last run: {', '.join(bits) if bits else 'nothing changed'}.")
    lines += ["- Nothing is accepted, ignored or reported until you say so.", ""]

    banner = _sample_data_banner([inv.public_url or inv.name for inv, _, _ in analyzed])
    if banner:
        lines += [banner, ""]

    n = 0
    if accept:
        lines += [f"## Accept ({len(accept)})", ""]
        for inv, g, _ins in accept[:MAX_NAMED]:
            n += 1
            lines += _person_block(n, inv, g, cfg, in_dms=inv.key in dm_keys)
        if len(accept) > MAX_NAMED:
            lines += [f"...and {len(accept) - MAX_NAMED} more in {csv_path.name}, "
                      "same ranking.", ""]

    if decide:
        lines += [f"## Your call ({len(decide)})", "",
                  "Press, competitors, legal, or someone claiming they already spoke to you. "
                  "Never auto-accepted, never auto-ignored.", ""]
        for inv, g, _ins in decide[:MAX_NAMED]:
            n += 1
            lines += _person_block(n, inv, g, cfg, in_dms=inv.key in dm_keys)
        if len(decide) > MAX_NAMED:
            lines += [f"...and {len(decide) - MAX_NAMED} more in {csv_path.name}.", ""]

    if talent:
        lines += [f"## Talent lane ({len(talent)})", "",
                  "Applied, and there is something behind the application. "
                  "Not buyers — route them to whoever owns the role.", ""]
        for inv, g, _ins in talent[:8]:
            lines.append(f"- **{inv.name or 'Unknown'}** — {g.summary}")
        if len(talent) > 8:
            lines.append(f"- ...and {len(talent) - 8} more in {csv_path.name}.")
        lines.append("")

    if ignore:
        lines += [f"## Spam — ignored only on your word ({len(ignore)})", "",
                  f"{_lane_phrase([g for _, g, _ in ignore]).capitalize()}. "
                  "Nothing happens until you say so, and ignoring is reversible — "
                  "they can invite you again.", ""]
        for camp in camps:
            lines.append(f"- **{camp.size} of these are one sequence** — one judgment, not "
                         f'{camp.size}. Sample: "{camp.sample[:110]}"')
        for inv, g, _ins in ignore[:6]:
            lines.append(f"- {inv.name or 'Unknown'} — {g.summary}")
        if len(ignore) > 6:
            lines.append(f"- ...and {len(ignore) - 6} more, all listed in {csv_path.name}.")
        lines += ["", 'Say **"clean up the spam"** to queue these in batches of 25.', ""]

    if identify:
        lines += [f"## Worth 30 seconds to identify ({len(identify)})", "",
                  "Commercial intent, but no company we can attribute it to. "
                  "The next step is a lookup, not a reply in the dark.", ""]
        for inv, _g, _ins in identify[:8]:
            note = " ".join((inv.note or inv.headline or "").split())[:110]
            lines.append(f'- **{inv.name or "Unknown"}** — "{note}"')
        lines.append("")

    if other > 0:
        lines += [f"## Everything else ({other})", "",
                  "ICP-adjacent, no decisive signal, nothing owed. Ranked by score in "
                  f"`{csv_path.name}` — read the top rows if you want more volume.", ""]

    lines += ["Reply draft these when you want me to prepare actions.", ""]
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
                "Run the tool again against your own account and they are "
                "replaced — it fetches the real data itself.")
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
        f"# LinkedIn messages — {cfg.today.strftime('%d %b %Y')}",
        "",
        "type: reminder-card",
        f"source: {source}",
        f"items: {len(analyzed)} thread(s) — "
        + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())),
        "",
        "## TL;DR",
        "",
    ]
    # The lead is what it costs to keep ignoring this, in the order it costs.
    todo = len(escalations) + len(owed_us) + len(waiting) + len(holds)
    lines.append(f"- **{len(analyzed)} threads. {todo} need you.**")
    if escalations:
        lines.append(f"- **Answer personally ({len(escalations)})** — "
                     + ", ".join(f"{c.counterparty or 'Unknown'}" for c, _, _ in escalations[:3])
                     + ". Money, legal, security or churn — not delegatable.")
    if owed_us:
        late = max((x.days_overdue for _, _, i in owed_us for x in i.open_commitments), default=0)
        chased = sum(1 for _, _, i in owed_us if any(x.chased for x in i.open_commitments))
        lines.append(f"- **You promised {len(owed_us)} people something** and have not sent it. "
                     f"Oldest is {late}d overdue"
                     + (f"; {chased} chased you about it." if chased else "."))
    overdue = [d for _, _, _, d in clocks if d.status(cfg.today).startswith("passed")]
    if clocks:
        lines.append(f"- **{len(clocks)} deadlines** they set"
                     + (f", {len(overdue)} already passed." if overdue else "."))
    if waiting:
        lines.append(f"- **{len(waiting)} waiting on a reply** with nothing promised yet.")
    if holds:
        lines.append(f"- **{len(holds)} for you personally** — press, investors, competitors or legal.")
    if counts.get("trash"):
        lines.append(f"- **{counts['trash']} cold pitches** — say \"clean up my LinkedIn DMs\" "
                     "and I will queue them to archive.")
    lines += ["- Nothing is replied to, archived or reported until you say so.",
              f"- Full population: {csv_path.name}", ""]
    banner = _sample_data_banner([c.counterparty_url or c.counterparty for c, _, _ in analyzed])
    if banner:
        lines += [banner, ""]
    # Whose inbox this is, and how that was decided. If this line is wrong, every
    # direction in the report is wrong — and it would otherwise look fine.
    owner, how = last_owner()
    if owner:
        lines += [f"Reading as: **{owner}** ({how}). "
                  "If that is not you, every direction below is inverted — "
                  "fix the Name line in memory/ceo-persona.md.", ""]
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
        """Name, and what they are — not the internal score.

        `ins.value.line()` renders as "critical (118) — open deal in the CRM".
        The parenthesised number is ours, not theirs; it belongs in the CSV.
        """
        who = convo.counterparty or "Unknown"
        v = ins.value
        why = v.identified_by or (v.facts or v.signals or [""])[0]
        if v.needs_identification:
            why = (why + " — worth identifying").lstrip(" —")
        return f"**{who}**" + (f" — {why}" if why else "")

    if escalations:
        head("Answer personally",
             "Money, legal, security, churn or safety. Never templated, never delegated.")
        lines.append("")
        for convo, g, ins in escalations[:MAX_NAMED]:
            lines.append(f"{person(convo, ins)} — {'; '.join(g.reasons[:2])}")
            last = (sorted(convo.inbound, key=lambda m: (m.at or cfg.today))[-1].body
                    if convo.inbound else "")
            if last:
                lines.append(f'> "{" ".join(last.split())[:180]}"')
            lines.append(f"Do: {g.action} · {ins.state.summary}")
            lines.append("")

    if owed_us:
        head("You promised, and it never went out",
             "Ranked by what it costs to keep breaking them. Promises already "
             "delivered, and vague ones with no named subject, are filtered out.")
        lines.append("")
        for convo, g, ins in owed_us[:MAX_NAMED]:
            for c in ins.open_commitments[:2]:
                chased = " — **and they chased you**" if c.chased else ""
                lines.append(f"- **{convo.counterparty or 'Unknown'}** — "
                             f"{c.kind}, {c.days_overdue}d ago{chased}")
                lines.append(f'    "{c.quote}"')
        lines.append("")

    if clocks:
        head("Deadlines they set",
             '"Before Friday" is resolved against the day it was written, not today.')
        lines.append("")
        for convo, g, ins, d in clocks[:MAX_NAMED]:
            lines.append(f'- **{convo.counterparty or "Unknown"}** — "{d.phrase}" '
                         f"= {d.due} ({d.status(cfg.today)})")
        lines.append("")

    if waiting:
        head("Waiting on you", "They wrote last and never got an answer.")
        lines.append("")
        for convo, g, ins in waiting[:MAX_NAMED]:
            lines.append(f"- {person(convo, ins)} — {convo.days_waiting(cfg.today)}d, "
                         f"{ins.state.stage}")
            last = (sorted(convo.inbound, key=lambda m: (m.at or cfg.today))[-1].body
                    if convo.inbound else "")
            if last:
                lines.append(f'    "{" ".join(last.split())[:150]}"')
        lines.append("")

    if holds:
        head("Your call", "Press, investors, competitors or legal. These never auto-resolve.")
        lines.append("")
        for convo, g, ins in holds[:MAX_NAMED]:
            lines.append(f"- **{convo.counterparty or 'Unknown'}** — "
                         f"{'; '.join(g.reasons[:2])}. {g.action}")
        lines.append("")

    for camp in camps:
        head(f"{camp.size} senders, one sequence",
             f"One judgment, not {camp.size}. Archive the whole cluster or none of it.")
        lines.append(f'> "{camp.sample}"')
        lines.append("")

    # The spam and no-action counts are already in the TL;DR. Repeating them as
    # sections at the bottom is the padding that made this read like filler.
    solo_spam = counts.get("trash", 0) - len(camp_members)

    if diff.still_waiting:
        head("Longest unanswered")
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
