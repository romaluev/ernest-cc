"""Deterministic HTML digest of the day's output.

The engine's cards are already fixed-format markdown. This renders them into ONE
clean, consistently-styled HTML page the CEO opens — same layout every time, no
LLM variance, no third-party dependencies. Print-to-PDF from the browser.
"""
from __future__ import annotations

import html
import re
from datetime import date
from pathlib import Path
from typing import List, Optional

from .config import Config, ensure_dirs

# Fixed reading order; anything else follows, sorted, so the page is stable.
_PRIORITY = [
    "brief",
    "b2b-grades",
    "talent-grades",
    "mail-audit",
    "dropped-followups",
    "important-followups",
    "slack-open-threads",
    "inbox-prospects",
]

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_TIER = re.compile(r"\[(TIER-1|TIER-2|TIER-3|TRASH)\]")
_META = re.compile(r"^[A-Za-z][\w .\-/]*:\s")

_CSS = """
:root { --fg:#1c2024; --mut:#6b7280; --line:#e5e7eb; --bg:#f6f7f9; --card:#fff; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
.wrap { max-width:820px; margin:0 auto; padding:32px 20px 64px; }
header.top { margin-bottom:20px; }
header.top h1 { font-size:22px; margin:0 0 4px; }
header.top .sub { color:var(--mut); font-size:13px; }
section.card { background:var(--card); border:1px solid var(--line); border-radius:12px;
  padding:18px 20px; margin:16px 0; box-shadow:0 1px 2px rgba(16,24,40,.04); }
section.card > h2 { font-size:17px; margin:0 0 12px; padding-bottom:8px; border-bottom:1px solid var(--line); }
section.card h3 { font-size:14px; margin:16px 0 6px; color:#111827; }
section.card h4 { font-size:13px; margin:12px 0 4px; color:#374151; }
ul { margin:6px 0 6px; padding-left:20px; }
li { margin:3px 0; }
p { margin:6px 0; }
.meta { display:flex; flex-wrap:wrap; gap:6px 14px; margin:0 0 6px; color:var(--mut); font-size:12.5px; }
.meta .k { color:#9ca3af; }
.badge { display:inline-block; font-size:11px; font-weight:700; letter-spacing:.03em;
  padding:2px 8px; border-radius:999px; margin-right:6px; vertical-align:1px; }
.t1 { background:#e6f6ec; color:#137333; }
.t2 { background:#fef3e2; color:#9a5b00; }
.t3 { background:#eef0f2; color:#4b5563; }
.trash { background:#fdecec; color:#b3261e; }
footer.foot { color:var(--mut); font-size:12px; margin-top:24px; text-align:center; }
@media print { body{background:#fff;} section.card{box-shadow:none;} }
"""

_BADGE_CLASS = {"TIER-1": "t1", "TIER-2": "t2", "TIER-3": "t3", "TRASH": "trash"}


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


def render_html(cfg: Config, day: Optional[date] = None) -> str:
    day = day or cfg.today
    files = _ordered_files(cfg, day)
    cards = []
    for path in files:
        try:
            body = _md_to_html(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        cards.append(f'<section class="card">{body}</section>')
    if not cards:
        cards.append('<section class="card"><p>Nothing to show for today. '
                     'Run <code>ernest start</code> first.</p></section>')
    return (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>Ernest digest — {day.isoformat()}</title><style>{_CSS}</style></head>"
        "<body><div class=\"wrap\">"
        f'<header class="top"><h1>Ernest — daily digest</h1>'
        f'<div class="sub">{day.isoformat()} · consistent view, generated by the engine</div></header>'
        + "\n".join(cards)
        + '<footer class="foot">Read-only summary. Print to PDF from your browser to share.</footer>'
        "</div></body></html>\n"
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


_CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
)


def to_pdf(html_path: Path) -> Optional[Path]:
    """Best-effort HTML -> PDF using a tool already on the machine.

    Tries wkhtmltopdf, then headless Chrome/Chromium. Returns the PDF path on
    success, or None so the caller can fall back to "Print to PDF" from a browser.
    No dependency is required; this is purely opportunistic.
    """
    import shutil
    import subprocess

    pdf_path = html_path.with_suffix(".pdf")

    wk = shutil.which("wkhtmltopdf")
    if wk:
        try:
            subprocess.run([wk, "-q", str(html_path), str(pdf_path)],
                           check=True, capture_output=True, timeout=60)
            if pdf_path.is_file():
                return pdf_path
        except (subprocess.SubprocessError, OSError):
            pass

    for cand in _CHROME_CANDIDATES:
        chrome = cand if Path(cand).exists() else shutil.which(cand)
        if not chrome:
            continue
        try:
            subprocess.run(
                [chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                 f"--print-to-pdf={pdf_path}", html_path.as_uri()],
                check=True, capture_output=True, timeout=60)
            if pdf_path.is_file():
                return pdf_path
        except (subprocess.SubprocessError, OSError):
            continue
    return None
