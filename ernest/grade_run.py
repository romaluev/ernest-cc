"""Run tier grading over real data and write sorted grade cards.

B2B: grade inbound mail threads (CRM tier > lists > inference).
Talent: grade sourcing rows (purpose=hire) against the ex-Skolkovo rubric.
Cards are remind/assign only — grading never sends or mutates anything.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import Config, ensure_dirs
from .grading import Grade, grade_b2b, grade_talent, pool_name
from .sources import Contact, Thread, load_contacts, load_threads

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
    out.sort(key=lambda pair: (pair[1].rank, -(pair[0].days_waiting(cfg.today))))
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
    out.sort(key=lambda pair: pair[1].rank)
    return out


def _grade_lines(grade: Grade) -> List[str]:
    lines = [f"- tier: {grade.tier} (confidence: {grade.confidence})"]
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


def run(cfg: Config, *, b2b: bool = True, talent: bool = True) -> List[Path]:
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
    return written
