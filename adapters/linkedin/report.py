"""Render the two markdown cards into one page a person can actually read.

Markdown in a terminal is fine for an agent and poor for a CEO. This produces a
single self-contained HTML file — no external CSS, no webfonts, no network — and
a PDF when a Chromium-family browser is available to print it.

Deliberately not a markdown library: the cards are a known, narrow shape that
this project emits itself, so a 60-line renderer beats a dependency.
"""
from __future__ import annotations

import html
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

# Badges the cards emit, and what each should feel like at a glance.
_BADGE_CLASS = {
    "ESCALATION": "escalation", "YOU PROMISED": "escalation",
    "TIER-1": "tier1", "HOLD": "hold", "CLOCK": "hold",
    "IDENTIFY": "identify", "BOTH SURFACES": "both",
    "CAMPAIGN": "campaign", "BUCKET": "bucket",
}

_BADGE_STYLE = {
    "ESCALATION": ("#b3261e", "#fff"),
    "TIER-1": ("#0b6b5e", "#fff"),
    "HOLD": ("#8a5a00", "#fff"),
    "IDENTIFY": ("#2d4a8a", "#fff"),
    "CAMPAIGN": ("#5a4a7a", "#fff"),
    "BOTH SURFACES": ("#2d4a8a", "#fff"),
    "TIER-2": ("#5a6472", "#fff"),
    "BUCKET": ("#e8eaed", "#3c4043"),
    "CLOCK": ("#8a5a00", "#fff"),
    "WAITING": ("#5a6472", "#fff"),
    "YOU PROMISED": ("#b3261e", "#fff"),
    "AGING": ("#5a6472", "#fff"),
}

_CSS = """
:root{
  --ink:#14171a; --muted:#5f6b76; --line:#e4e8ec; --bg:#fff; --panel:#f7f9fb;
  --red:#b3261e; --teal:#0b6b5e; --amber:#8a5a00; --blue:#2d4a8a; --violet:#5a4a7a;
  --grey:#5a6472;
}
*{box-sizing:border-box}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;padding:0;background:var(--bg);color:var(--ink);
  font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif;
  font-feature-settings:"kern","liga","tnum"}
main{max-width:760px;margin:0 auto;padding:44px 28px 72px}

/* Masthead */
.mast{border-bottom:2px solid var(--ink);padding-bottom:14px;margin-bottom:22px}
.mast h1{margin:0;font-size:27px;letter-spacing:-.025em;font-weight:640}
.mast .sub{margin-top:5px;color:var(--muted);font-size:13px}
.mast .rule{margin-top:10px;font-size:12.5px;color:var(--muted)}
.mast .rule b{color:var(--ink)}

/* Summary strip */
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(96px,1fr));
  gap:8px;margin:0 0 26px}
.tile{border:1px solid var(--line);border-radius:9px;padding:10px 11px;background:var(--panel)}
.tile .n{font-size:21px;font-weight:660;letter-spacing:-.02em;line-height:1.1}
.tile .l{font-size:10.5px;text-transform:uppercase;letter-spacing:.055em;
  color:var(--muted);margin-top:3px}
.tile.hot .n{color:var(--red)} .tile.good .n{color:var(--teal)}
.tile.warn .n{color:var(--amber)}

/* Notices */
.note,.owner{border-radius:9px;padding:11px 14px;margin:0 0 16px;font-size:13px;
  border:1px solid}
.note{background:#fff8e6;border-color:#efd79a;color:#6b4e00}
.owner{background:#f2f6fc;border-color:#d5e1f4;color:#26456e}

/* Sections */
h2{font-size:12px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);
  margin:32px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}
h2:first-of-type{margin-top:8px}

/* Entries */
.item{border:1px solid var(--line);border-left:3px solid var(--grey);
  border-radius:0 9px 9px 0;padding:13px 15px;margin:9px 0;background:#fff;
  break-inside:avoid;page-break-inside:avoid}
.item.escalation{border-left-color:var(--red)}
.item.tier1{border-left-color:var(--teal)}
.item.hold{border-left-color:var(--amber)}
.item.identify,.item.both{border-left-color:var(--blue)}
.item.campaign{border-left-color:var(--violet)}
.item.bucket{border-left-color:var(--line);background:var(--panel)}
.head{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.badge{font-size:9.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
  padding:3px 7px;border-radius:4px;white-space:nowrap}
.who{font-weight:620;font-size:15px;letter-spacing:-.01em}
dl{margin:9px 0 0;display:grid;grid-template-columns:104px 1fr;gap:3px 12px}
dt{color:var(--muted);font-size:11.5px;text-transform:lowercase;padding-top:1px}
dd{margin:0;font-size:13px;word-break:break-word}
dd.action{font-weight:620}
dd.action::before{content:"→ ";color:var(--muted)}
blockquote{margin:9px 0 0;padding:8px 12px;border-left:2px solid var(--line);
  background:var(--panel);border-radius:0 6px 6px 0;color:#3a4148;font-size:12.5px;
  font-style:italic}
.plain{margin:7px 0 0;font-size:13px;color:#39414a}
code{font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;
  background:var(--panel);padding:1px 5px;border-radius:4px}
.foot{margin-top:38px;padding-top:14px;border-top:1px solid var(--line);
  color:var(--muted);font-size:11.5px}

@page{size:A4;margin:14mm 12mm}
@media print{
  main{padding:0;max-width:none}
  .mast{border-bottom-width:1.5px}
  h2{break-after:avoid;page-break-after:avoid}
}
@media(prefers-color-scheme:dark){
  :root{--ink:#e9edf1;--muted:#98a3ae;--line:#2a2f36;--bg:#15181c;--panel:#1b1f25}
  .item{background:#181c21}
  .note{background:#2a2410;border-color:#584a12;color:#e8d8a0}
  .owner{background:#161f33;border-color:#2a3c60;color:#bacef2}
  blockquote{color:#c6cdd4}
}
"""


def _inline(text: str) -> str:
    out = html.escape(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"`(.+?)`", r"<code>\1</code>", out)
    return out


def _badge(label: str) -> str:
    bg, fg = _BADGE_STYLE.get(label, ("#e8eaed", "#3c4043"))
    return f'<span class="badge" style="background:{bg};color:{fg}">{html.escape(label)}</span>'


# The card carries a machine header for agents (type/source/items/population)
# and a standing footer line. None of it belongs in a document a person reads —
# the provenance is lifted into the masthead instead.
_SKIP_PREFIX = ("type:", "source:", "items:", "Full population:",
                "Report only.", "Reply draft these when")


def _render_card(md: str) -> Tuple[str, List[str]]:
    """One card -> (html, notes). Body only; the page supplies its own chrome.

    An explicit dl-open flag rather than sniffing the previous fragment: the
    sniffing version opened a nested <dl> for every field and never closed one,
    which cascaded into a 48-page PDF where the content was indented off the
    right edge of the paper.
    """
    parts: List[str] = []
    item: List[str] = []
    cls = ""
    in_item = False
    dl_open = False

    def end_dl() -> None:
        nonlocal dl_open
        if dl_open:
            item.append("</dl>")
            dl_open = False

    def start_dl() -> None:
        nonlocal dl_open
        if not dl_open:
            item.append("<dl>")
            dl_open = True

    def close() -> None:
        nonlocal in_item, item, cls
        if in_item:
            end_dl()
            parts.append(f'<div class="item {cls}">' + "".join(item) + "</div>")
        item, in_item, cls = [], False, ""

    for raw in md.splitlines():
        line = raw.rstrip()
        if line.startswith("# ") or any(line.startswith(x) for x in _SKIP_PREFIX):
            continue
        if line.startswith("> "):
            close()
            parts.append(f'<div class="note">{_inline(line[2:])}</div>')
            continue
        if line.startswith("Reading as:"):
            close()
            parts.append(f'<div class="owner">{_inline(line)}</div>')
            continue

        m = re.match(r"^## \d+\.\s*(?:\[([A-Z0-9 -]+)\]\s*)?(.*)$", line)
        if m:
            close()
            in_item = True
            label = m.group(1) or ""
            cls = _BADGE_CLASS.get(label, "")
            badge = _badge(label) if label else ""
            item.append(f'<div class="head">{badge}'
                        f'<span class="who">{_inline(m.group(2))}</span></div>')
            continue

        if not line:
            continue

        if in_item:
            m = re.match(r"^- ([a-z_]+): (.*)$", line)
            if m:
                start_dl()
                key, val = m.group(1), m.group(2)
                extra = ' class="action"' if key == "action" else ""
                item.append(f"<dt>{html.escape(key)}</dt><dd{extra}>{_inline(val)}</dd>")
                continue
            if line.startswith("- "):
                start_dl()
                item.append(f"<dt></dt><dd>{_inline(line[2:])}</dd>")
                continue
            if line.startswith("    ") and line.strip().startswith('"'):
                end_dl()
                item.append(f"<blockquote>{_inline(line.strip())}</blockquote>")
                continue
            end_dl()
            item.append(f'<div class="plain">{_inline(line)}</div>')
            continue

        parts.append(f'<div class="plain">{_inline(line)}</div>')

    close()
    return "\n".join(parts), []


_SOURCE_LABEL = {
    "linkedin-archive": "LinkedIn data export",
    "linkedin-live": "read live from LinkedIn",
    "local-export": "a file already on this machine",
    "hubspot-mirror": "the CRM mirror (partial — not the whole queue)",
}

_TILE_ORDER = (("escalation", "Escalations", "hot"), ("tier-1", "Worth accepting", "good"),
               ("needs-reply", "Waiting on you", "warn"), ("hold", "Hold", "warn"),
               ("tier-2", "Worth a look", ""), ("trash", "Spam", ""))


def _provenance(md: str) -> Tuple[str, str]:
    """(source, 'since last run' line) — the two facts worth putting up top."""
    src = re.search(r"^source:\s*(.+)$", md, re.M)
    since = re.search(r"^Since the last run:\s*(.+)$", md, re.M)
    return (src.group(1).strip() if src else "",
            since.group(1).strip() if since else "")


def _counts(md: str) -> dict:
    """Pull the counts out of the card's own `items:` line rather than recounting."""
    m = re.search(r"^items:.*?—?\s*(.*)$", md, re.M)
    out: dict = {}
    if not m:
        return out
    for k, v in re.findall(r"([a-z0-9-]+):\s*(\d+)", m.group(1)):
        out[k] = out.get(k, 0) + int(v)
    return out


def _tiles(totals: dict) -> str:
    cells = []
    for key, label, tone in _TILE_ORDER:
        if not totals.get(key):
            continue
        cells.append(f'<div class="tile {tone}"><div class="n">{totals[key]}</div>'
                     f'<div class="l">{html.escape(label)}</div></div>')
    return f'<div class="tiles">{"".join(cells)}</div>' if cells else ""


def render_html(cards: List[Tuple[str, Path]], out: Path, *, when: str = "") -> Path:
    """cards: [(title, path-to-md)] -> one self-contained HTML file."""
    when = when or datetime.now().strftime("%A %d %B %Y").replace(" 0", " ")
    sections: List[str] = []
    totals: dict = {}
    sources: List[str] = []
    changes: List[str] = []
    for title, path in cards:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for k, v in _counts(text).items():
            totals[k] = totals.get(k, 0) + v
        src, since = _provenance(text)
        if src and src not in sources:
            sources.append(src)
        if since and since not in changes:
            changes.append(f"{title.lower()}: {since}")
        body, _ = _render_card(text)
        sections.append(f"<h2>{html.escape(title)}</h2>\n{body}")
    prov_bits = []
    if sources:
        prov_bits.append("Source: " + ", ".join(
            _SOURCE_LABEL.get(x, x) for x in sources))
    if changes:
        prov_bits.append("Since the last run — " + "; ".join(changes))
    prov = ('<div class="rule">' + html.escape(" · ".join(prov_bits)) + "</div>"
            if prov_bits else "")

    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LinkedIn inbound — {html.escape(when)}</title><style>{_CSS}</style></head>
<body><main>
<div class="mast">
  <h1>LinkedIn inbound</h1>
  <div class="sub">{html.escape(when)}</div>
  <div class="rule"><b>Report only.</b> Nothing was accepted, ignored, archived,
  or replied to. Actions happen when you approve a named list.</div>
  {prov}
</div>
{_tiles(totals)}
{"".join(sections)}
<div class="foot">Generated on this machine. No data left it.</div>
</main></body></html>"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    return out


def render_pdf(html_path: Path, out: Path) -> Optional[Path]:
    """Print the HTML to PDF via CDP. Returns None when no browser is reachable.

    A missing PDF is never an error — the HTML is the artifact and always exists.
    This is best-effort by design, and bounded: a browser that will not print
    must not be able to stall the run.
    """
    try:
        import browser                                        # type: ignore
    except Exception:                                         # noqa: BLE001
        return None
    drv = None
    try:
        drv = browser.open_driver("chrome")
    except Exception:                                         # noqa: BLE001
        # Nothing listening. Start one headlessly just for this.
        if not browser.launch_chromium(headless=True):
            return None
        try:
            drv = browser.open_driver("chrome", autolaunch=False)
        except Exception:                                     # noqa: BLE001
            return None
    try:
        ok = drv.print_pdf(html_path.as_uri(), out)
    except Exception:                                         # noqa: BLE001
        ok = False
    finally:
        try:
            drv.close()
        except Exception:                                     # noqa: BLE001
            pass
    return out if ok and out.is_file() else None
