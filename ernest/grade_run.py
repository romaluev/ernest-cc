"""Run tier grading over real data and write sorted grade cards.

B2B: grade inbound mail threads (CRM tier > lists > inference).
Talent: grade sourcing rows (purpose=hire) against the ex-NovaLabs rubric.
Cards are remind/assign only — grading never sends or mutates anything.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import Config, ensure_dirs
from .grading import (Grade, LinkedInGrade, grade_b2b, grade_linkedin_inbound,
                      grade_talent, pool_name)
from .sources import (Contact, Invitation, Thread, load_contacts,
                      load_invitations, load_threads)

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


def _linkedin_card(cfg: Config, graded: List[Tuple[Invitation, LinkedInGrade]],
                   csv_path: Path) -> str:
    counts: Dict[str, int] = {}
    for _, g in graded:
        counts[g.tier] = counts.get(g.tier, 0) + 1
    source = graded[0][0].source if graded else "local-export"

    named = [pair for pair in graded if pair[1].tier in ("hold", "tier-1")][:MAX_NAMED]
    named_keys = {inv.key for inv, _ in named}
    overflow: Dict[str, int] = {}
    for inv, g in graded:
        if inv.key not in named_keys:
            overflow[g.tier] = overflow.get(g.tier, 0) + 1

    summary = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    sections = len(named) + len([t for t in overflow if overflow[t]])
    lines = [
        f"# Watch: linkedin-invitations ({cfg.today.isoformat()})",
        "",
        "type: reminder-card",
        f"source: {source}",
        f"items: {sections} (population {len(graded)}; {summary})",
        "",
        "Report only. Nothing is accepted, ignored, or reported until you say so.",
        f"Full population: {csv_path.name}",
        "",
    ]
    n = 0
    for inv, g in named:
        n += 1
        who = inv.name or "Unknown"
        if inv.company:
            who += f" - {inv.company}"
        lines.append(f"## {n}. [{g.tier.upper()}] {who}")
        lines.append(f"- tier: {g.tier} (confidence: {g.confidence}, match score: {int(g.score)})")
        lines.append(f"- signal: {g.signal}")
        lines.append("- channel: Connection Request")
        if inv.public_url:
            lines.append(f"- linkedin: {inv.public_url}")
        if inv.sent_at:
            lines.append(f"- waiting: {inv.days_waiting(cfg.today)}d")
        if inv.note:
            note = inv.note if len(inv.note) <= 160 else inv.note[:157] + "..."
            lines.append(f'- note: "{note}"')
        lines.append(f"- why: {'; '.join(g.reasons) or 'No decisive signal'}")
        lines.append(f"- action: {g.action}")
        if g.flags:
            lines.append(f"- check: {'; '.join(g.flags)}")
        if g.tier == "tier-1" and g.action == "Accept":
            lines.append("- crm: PROPOSE linkedin_inbound_invitation_status=Accepted")
        lines.append("")

    for tier in ("hold", "tier-1", "tier-2", "trash"):
        count = overflow.get(tier, 0)
        if not count:
            continue
        n += 1
        title, why, action = _BUCKET_COPY.get(
            tier, (f"{tier} — not shown individually",
                   "Above the on-card display limit.",
                   "Read the rows in {csv}."))
        if tier in ("hold", "tier-1"):
            title = f"{tier.upper()} above the display limit"
            why = f"{count} more scored {tier}; only the top {MAX_NAMED} are named on the card."
            action = "Read the top rows in {csv} — these still need a person."
        lines.append(f"## {n}. [BUCKET] {title} ({count})")
        lines.append(f"- count: {count}")
        if tier == "trash":
            lines.append("- signal: Spam")
        lines.append(f"- why: {why}")
        lines.append(f"- action: {action.format(csv=csv_path.name)}")
        lines.append("")

    lines.append('Reply draft these when you want me to prepare actions.')
    lines.append("")
    return "\n".join(lines)


def run(cfg: Config, *, b2b: bool = True, talent: bool = True,
        linkedin: bool = True) -> List[Path]:
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
        graded_l = grade_invitations(cfg)
        if graded_l:
            sidecar = _li_sidecar(cfg, graded_l)
            path = cfg.watch_dir / f"linkedin-invitations--{cfg.today.isoformat()}.md"
            path.write_text(_linkedin_card(cfg, graded_l, sidecar), encoding="utf-8")
            written += [path, sidecar]
    return written
