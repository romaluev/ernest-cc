"""Assemble reply briefs for the people actually worth replying to.

The engine has no model and does not write the prose. A template-generated reply
in someone else's voice is worse than no reply — it is the exact thing that makes
an inbox feel automated. What this produces is the BRIEF: their real question,
what we already promised, the clock, where the thread stands, what the reply must
contain, and what it must not claim.

An agent (or a person) writes from that. Nothing is ever sent.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import List

MAX_DRAFTS = 10


def write_drafts(cfg, analyzed, out: Path, *, limit: int = MAX_DRAFTS) -> Path:
    """One markdown file of briefs, ordered by what it costs to keep ignoring."""
    from ernest import li_insight

    # Escalations first, then unkept promises, then whoever has waited longest —
    # weighted by what the counterparty is actually worth.
    def priority(t):
        convo, grade, ins = t
        rank = {"escalation": 0, "needs-reply": 1, "hold": 2}.get(grade.bucket, 9)
        promised = 0 if ins.open_commitments else 1
        return (rank, promised, ins.value.rank, -convo.days_waiting(cfg.today))

    picks = [t for t in sorted(analyzed, key=priority)
             if t[1].bucket in ("escalation", "needs-reply")][:limit]

    lines: List[str] = [
        f"# Reply briefs — {cfg.today.isoformat()}",
        "",
        "STATUS: DRAFT — nothing here has been sent, and nothing will be without",
        "your approval. These are briefs, not finished replies: each one lists what",
        "the reply must contain and what it must not claim. Write them in your own",
        "voice, or ask your assistant to draft from the brief.",
        "",
    ]
    if not picks:
        lines += ["Nobody is waiting on a reply right now.", ""]
    for convo, grade, ins in picks:
        brief = li_insight.reply_brief(
            counterparty=convo.counterparty or "Unknown",
            messages=convo.messages, value=ins.value, state=ins.state,
            open_commitments=ins.open_commitments, due=ins.live_deadlines,
            today=cfg.today, thread_id=convo.id)
        lines.append(brief.to_markdown())
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("The six things a good reply does: one reason for writing tied to their")
    lines.append("last message · one verifiable proof point · one low-friction next step ·")
    lines.append("every claim source-backed or marked unknown · no fake familiarity ·")
    lines.append("grounded in the whole thread, not the last line.")
    lines.append("")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
