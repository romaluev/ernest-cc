#!/usr/bin/env python3
"""HTML digest renderer: deterministic, safe, consistently ordered."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FAILURES: list[str] = []


def check(label: str, condition: bool) -> None:
    print(f"  [{'ok  ' if condition else 'FAIL'}] {label}")
    if not condition:
        FAILURES.append(label)


def main() -> int:
    profile = Path(tempfile.mkdtemp(prefix="ernest_render_profile_"))
    vault = Path(tempfile.mkdtemp(prefix="ernest_render_vault_"))
    shutil.copytree(ROOT / "memory", profile / "memory")
    shutil.copytree(ROOT / "data", profile / "data")

    env = os.environ.copy()
    env.update({
        "ERNEST_PROFILE_DIR": str(profile),
        "ERNEST_LOCAL_VAULT": str(vault),
        "ERNEST_MODE": "local",
        "ERNEST_TODAY": "2026-06-25",
        "ERNEST_NO_OPEN": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    })

    def run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "ernest.cli", *args],
            cwd=str(ROOT), env=env, text=True, capture_output=True, check=False)

    start = run("start")
    check("start exits 0", start.returncode == 0)
    if start.returncode != 0:
        print(start.stderr)
    check("start mentions clean digest", "digest" in start.stdout.lower())

    digest = vault / "Ernest" / "00-Daily" / "digest--2026-06-25.html"
    check("start writes the html digest", digest.exists())

    render = run("render")
    check("render exits 0", render.returncode == 0)

    if digest.exists():
        html = digest.read_text(encoding="utf-8")
        check("is a full html document", html.startswith("<!doctype html>"))
        check("has the fixed digest header", "Ernest — daily digest" in html)
        check("pamphlet sheets", 'class="sheet has-rail"' in html)
        check("bottom line on page 1", html.find("Bottom line") < html.find("Morning brief"))
        check("top 3 on page 1", html.find("Top 3") < html.find("Morning brief"))
        check("renders cards", '<section class="card">' in html)
        check("colorizes tier badges", 'class="badge t1"' in html)
        # Brief must come before grade cards (fixed reading order).
        check("brief precedes b2b grades",
              html.find("Morning brief") < html.find("B2B lead grades"))
        # Deterministic: rendering twice yields identical bytes.
        second = run("render")
        check("render is deterministic",
              second.returncode == 0 and digest.read_text(encoding="utf-8") == html)
        # No raw markdown bullets or unescaped angle brackets leaking through.
        check("escapes thread arrows", "-&gt;" in html or "->" not in html)

    pdf_run = run("render", "--pdf")
    pdf = vault / "Ernest" / "00-Daily" / "digest--2026-06-25.pdf"
    check("render --pdf exits 0", pdf_run.returncode == 0)
    if pdf.exists() and pdf.stat().st_size > 0:
        blob = pdf.read_bytes()
        check("writes a dated PDF next to the digest", blob.startswith(b"%PDF"))
        check("did not fall back to Print-to-PDF",
              "Print -> Save as PDF" not in pdf_run.stdout)
        pdftotext = shutil.which("pdftotext")
        if pdftotext:
            extracted = subprocess.run(
                [pdftotext, "-f", "1", "-l", "1", "-layout", str(pdf), "-"],
                text=True, capture_output=True, check=False)
            page1 = extracted.stdout.lower()
            check("PDF page 1 has Bottom line", "bottom line" in page1)
            check("PDF page 1 has Top 3", "top 3" in page1)
        else:
            print("  [skip] pdftotext not installed; HTML already has page-1 Bottom line")
    else:
        from ernest.pdf.chrome import chrome_binaries
        if chrome_binaries() or shutil.which("wkhtmltopdf"):
            check("render --pdf writes a PDF when a printer exists", False)
        else:
            print("  [skip] no Chrome / headless shell / wkhtmltopdf on this machine")

    if FAILURES:
        print("FAILED render tests:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("PASS - html digest renderer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
