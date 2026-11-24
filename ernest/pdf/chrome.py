"""A4 pamphlet CSS + headless print. Self-contained — do not import linkedin_research."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

REPO = Path(__file__).resolve().parents[2]
ASSETS = REPO / "assets"
FONTS = ASSETS / "fonts"
CSS_PATH = ASSETS / "pdf" / "brief.css"

_APP_CHROME = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
)
_WHICH_CHROME = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "chrome-headless-shell",
)


def pamphlet_css() -> str:
    """Load brief.css and point @font-face at this checkout's fonts."""
    raw = CSS_PATH.read_text(encoding="utf-8") if CSS_PATH.is_file() else ""
    if FONTS.is_dir():
        base = FONTS.resolve().as_uri().rstrip("/")
        raw = raw.replace('url("fonts/', f'url("{base}/')
        raw = raw.replace("url('fonts/", f"url('{base}/")
    return raw


def chrome_binaries() -> List[str]:
    """Prefer the same Playwright headless shell LinkedIn research uses."""
    found: List[str] = []
    cache = Path.home() / "Library" / "Caches" / "ms-playwright"
    if cache.is_dir():
        for path in sorted(cache.glob(
                "chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell")):
            if path.is_file():
                found.append(str(path))
    for cand in _APP_CHROME:
        if Path(cand).is_file():
            found.append(cand)
    for name in _WHICH_CHROME:
        hit = shutil.which(name)
        if hit:
            found.append(hit)
    # Dedup, keep order.
    out: List[str] = []
    seen = set()
    for item in found:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def to_pdf(html_path: Path) -> Optional[Path]:
    """Print the digest HTML to a sibling .pdf. None if no headless chrome/wkhtmltopdf."""
    pdf_path = html_path.with_suffix(".pdf")
    uri = html_path.resolve().as_uri()

    for chrome in chrome_binaries():
        if _print_chrome(chrome, uri, pdf_path):
            return pdf_path

    wk = shutil.which("wkhtmltopdf")
    if wk:
        try:
            subprocess.run(
                [wk, "-q", "--enable-local-file-access", str(html_path), str(pdf_path)],
                check=True, capture_output=True, timeout=90,
            )
            if pdf_path.is_file() and pdf_path.stat().st_size > 0:
                return pdf_path
        except (subprocess.SubprocessError, OSError):
            pass
    return None


def _print_chrome(chrome: str, uri: str, pdf_path: Path) -> bool:
    args_sets = (
        [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         "--virtual-time-budget=8000", f"--print-to-pdf={pdf_path}", uri],
        [chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
         "--virtual-time-budget=8000", f"--print-to-pdf={pdf_path}", uri],
    )
    for args in args_sets:
        try:
            subprocess.run(args, check=True, capture_output=True, timeout=90)
            if pdf_path.is_file() and pdf_path.stat().st_size > 0:
                return True
        except (subprocess.SubprocessError, OSError):
            if pdf_path.exists() and pdf_path.stat().st_size == 0:
                try:
                    pdf_path.unlink()
                except OSError:
                    pass
            continue
    return False
