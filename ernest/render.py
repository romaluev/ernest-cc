"""Deterministic pamphlet digest of the day's output.

Cards stay fixed-format markdown. The HTML is the source; PDF is the shareable
A4 artifact (teal rail, same type contract as Higgsfield LinkedIn research).
"""
from __future__ import annotations

import html
import re
from datetime import date
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from .config import Config, ensure_dirs
from .pdf.chrome import pamphlet_css
from .pdf.chrome import to_pdf as html_to_pdf

# Fixed reading order; anything else follows, sorted, so the page is stable.
_PRIORITY = [
    "brief",
    "b2b-grades",
    "linkedin-invitations",
    "talent-grades",
    "mail-audit",
    "dropped-followups",
    "important-followups",
    "slack-open-threads",
    "inbox-prospects",
]

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_TIER = re.compile(r"\[(TIER-1|TIER-2|TIER-3|TRASH|HOLD|BUCKET)\]")
_META = re.compile(r"^[A-Za-z][\w .\-/]*:\s")
_HEADING = re.compile(r"^##\s+(.+?)\s*$")

_BADGE_CLASS = {"TIER-1": "t1", "TIER-2": "t2", "TIER-3": "t3", "TRASH": "trash",
                "HOLD": "hold", "BUCKET": "bucket"}
# Cover is one screen. Remaining cards flow in a single pack (Chrome paginates).


def _inline(text: str) -> str:
    out = html.escape(text)
    out = _BOLD.sub(r"<strong>\1</strong>", out)
    out = _TIER.sub(
        lambda m: f'<span class="badge {_BADGE_CLASS[m.group(1)]}">{m.group(1)}</span>', out)
    return out


def _md_to_html(text: str) -> str:
    """Convert our card dialect to safe HTML. Deterministic, line-based."""
    lines = text.splitlines()
    out: List[str] = []
    in_list = False
    meta: List[str] = []

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    def flush_meta() -> None:
        if meta:
            out.append('<div class="meta">' + "".join(meta) + "</div>")
            meta.clear()

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            close_list()
            flush_meta()
            continue
        if stripped.startswith("# "):
            close_list(); flush_meta()
            out.append(f"<h2>{_inline(stripped[2:])}</h2>")
        elif stripped.startswith("### "):
            close_list(); flush_meta()
            out.append(f"<h4>{_inline(stripped[4:])}</h4>")
        elif stripped.startswith("## "):
            close_list(); flush_meta()
            out.append(f"<h3>{_inline(stripped[3:])}</h3>")
        elif stripped.startswith("- "):
            flush_meta()
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append(f"<li>{_inline(stripped[2:])}</li>")
        elif _META.match(stripped) and not in_list:
            key, _, val = stripped.partition(":")
            meta.append(f'<span><span class="k">{html.escape(key)}:</span> {_inline(val.strip())}</span>')
        else:
            close_list(); flush_meta()
            out.append(f"<p>{_inline(stripped)}</p>")
    close_list(); flush_meta()
    return "\n".join(out)


def _ordered_files(cfg: Config, day: date) -> List[Path]:
    stamp = day.isoformat()
    found: List[Path] = []
    for d in (cfg.daily_dir, cfg.watch_dir):
        if d.is_dir():
            found += [p for p in d.glob(f"*--{stamp}.md")]

    def rank(p: Path) -> tuple[int, str]:
        for i, prefix in enumerate(_PRIORITY):
            if p.name.startswith(prefix):
                return (i, p.name)
        return (len(_PRIORITY), p.name)

    return sorted(found, key=rank)


def _section_bullets(md: str, titles: Sequence[str]) -> List[str]:
    want = {t.lower() for t in titles}
    lines = md.splitlines()
    grab = False
    out: List[str] = []
    for raw in lines:
        stripped = raw.strip()
        match = _HEADING.match(stripped)
        if match:
            if grab:
                break
            grab = match.group(1).lower() in want
            continue
        if grab and stripped.startswith("- "):
            out.append(stripped[2:].strip())
    return out


def _hero_bits(files: Sequence[Path]) -> Tuple[List[str], List[str]]:
    """Bottom line + Top 3 from today's brief (or a stable fallback)."""
    brief = next((p for p in files if p.name.startswith("brief")), None)
    if brief is None:
        return ["Nothing to show for today. Run `ernest start` first."], []
    try:
        md = brief.read_text(encoding="utf-8")
    except OSError:
        return ["Nothing to show for today. Run `ernest start` first."], []
    bottom = _section_bullets(md, ("Bottom line",))
    top3 = _section_bullets(md, ("Top 3", "Top 3 actions"))
    if not bottom:
        needs = _section_bullets(md, ("Needs you today",))
        if needs:
            bottom = [needs[0]]
            top3 = top3 or needs[:3]
        else:
            bottom = ["Open the digest."]
    return bottom[:2], top3[:3]


def _list_html(items: Sequence[str], ordered: bool) -> str:
    if not items:
        return "<p class=\"note\">—</p>"
    tag = "ol" if ordered else "ul"
    body = "\n".join(f"<li>{_inline(item)}</li>" for item in items)
    return f"<{tag}>{body}</{tag}>"


def _sheet(inner: str, page: int, total: int, day: date, *, cover: bool = False) -> str:
    stamp = day.isoformat()
    cls = "sheet has-rail cover" if cover else "sheet has-rail"
    return (
        f'<section class="{cls}">'
        f'<div class="rail"><span>Ernest · Alex Mashrabov · {stamp}</span></div>'
        f'<div class="inner with-rail">{inner}</div>'
        f'<footer class="foot"><span>CEO brief · {stamp}</span>'
        f"<span>Read-only digest</span><span>{page} / {total}</span></footer>"
        "</section>"
    )


def _hero_inner(day: date, bottom: Sequence[str], top3: Sequence[str]) -> str:
    if len(bottom) == 1:
        bottom_body = f'<p class="lede">{_inline(bottom[0])}</p>'
    else:
        bottom_body = _list_html(bottom, ordered=False)
    return (
        '<p class="kicker">CEO brief</p>'
        "<h1>Ernest — daily digest</h1>"
        f'<p class="lede">{day.isoformat()} · one screen, then the rest</p>'
        '<div class="hero">'
        '<div class="hero-block"><h2>Bottom line</h2>'
        f"{bottom_body}</div>"
        '<div class="hero-block"><h2>Top 3</h2>'
        f"{_list_html(top3, ordered=True)}</div>"
        "</div>"
    )


def render_html(cfg: Config, day: Optional[date] = None) -> str:
    day = day or cfg.today
    files = _ordered_files(cfg, day)
    cards: List[str] = []
    for path in files:
        try:
            body = _md_to_html(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        cards.append(f'<section class="card">{body}</section>')
    if not cards:
        cards.append('<section class="card"><p>Nothing to show for today. '
                     'Run <code>ernest start</code> first.</p></section>')

    bottom, top3 = _hero_bits(files)
    inners = [_hero_inner(day, bottom, top3), "\n".join(cards)]
    total = len(inners)
    sheets = [
        _sheet(inner, i, total, day, cover=(i == 1))
        for i, inner in enumerate(inners, 1)
    ]
    css = pamphlet_css()
    return (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>Ernest digest — {day.isoformat()}</title><style>{css}</style></head>"
        f"<body>{''.join(sheets)}</body></html>\n"
    )


def run(cfg: Config, day: Optional[date] = None) -> Path:
    ensure_dirs(cfg)
    day = day or cfg.today
    path = cfg.daily_dir / f"digest--{day.isoformat()}.html"
    path.write_text(render_html(cfg, day), encoding="utf-8")
    return path


def open_in_browser(path: Path) -> bool:
    import os
    import webbrowser
    if os.environ.get("ERNEST_NO_OPEN"):
        return False
    try:
        return webbrowser.open(path.as_uri())
    except Exception:  # noqa: BLE001 - opening is best-effort
        return False


def to_pdf(html_path: Path) -> Optional[Path]:
    """HTML → dated sibling PDF via the pamphlet chrome printer."""
    return html_to_pdf(html_path)
