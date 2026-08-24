#!/usr/bin/env python3
"""LinkedIn inbound ingest — a fallback ladder, not a single integration.

    rung 1  cache        data/linkedin/*.csv is still fresh          -> use it
    rung 2  archive      LinkedIn's own "Get a copy of your data"    -> request + unpack
    rung 3  live         the invitation-manager DOM                  -> read (CAPPED) / act
    rung 4  hubspot      the linkedin_* properties HeyReach fills    -> partial mirror
    rung 5  unavailable  say so honestly                             -> never fabricate

Each rung records WHICH rung produced the data, and that label rides through to
the `source:` line on the report card. A reader must always be able to tell a
live read from a month-old snapshot from a partial CRM mirror.

RUNS OUTSIDE THE ERNEST GATE by design (see browser.py). The engine only reads
the files this writes.

Usage
    python3 adapters/linkedin/ingest.py --status --json
    python3 adapters/linkedin/ingest.py --from-archive ~/Downloads/Basic_LinkedInDataExport.zip
    python3 adapters/linkedin/ingest.py --rung 3 --limit 200
    python3 adapters/linkedin/ingest.py               # walk the whole ladder
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import browser  # noqa: E402
import cli_common as cc  # noqa: E402

CANONICAL_FIELDS = ["name", "public_url", "urn", "headline", "company", "location",
                    "note", "sent_at", "mutual_connections", "connections",
                    "invitation_type", "direction"]

RUNGS = {1: "local-export", 2: "linkedin-archive", 3: "linkedin-live",
         4: "hubspot-mirror", 5: "unavailable"}

# How many message rows the last archive import wrote, so the run can say so.
_LAST_MESSAGE_ROWS = 0

INVITATION_MANAGER = "https://www.linkedin.com/mynetwork/invitation-manager/received/"
DOWNLOAD_MY_DATA = "https://www.linkedin.com/mypreferences/d/download-my-data"

# The live rung mounts ~10 invitations per page load, so reading a large backlog
# means hundreds of automated page loads against a logged-in session. LinkedIn's
# own documented restriction triggers are about volume and burstiness of exactly
# that kind of activity — and there is no reason to take the risk, because the
# data export returns the whole queue in one download with no page loads at all.
#
# So the live rung is deliberately capped. It exists for small, current reads and
# for ACTING on approved batches, not for bulk import. Above the cap it refuses
# and names the safe path instead of quietly grinding through 700 page loads.
LIVE_READ_CAP = 200


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #

def identity_key(public_url: str = "", urn: str = "", name: str = "") -> str:
    """Mirror of `ernest.grading.identity_key`.

    Duplicated rather than imported: the adapter must run standalone, outside the
    engine and outside the gate. `tests/test_linkedin_ingest.py` asserts the two
    stay in agreement, so this copy cannot silently drift.
    """
    slug = ""
    if public_url:
        m = re.search(r"/in/([^/?#]+)", public_url.strip().rstrip("/"), re.I)
        slug = (m.group(1) if m else public_url.strip().rstrip("/").rsplit("/", 1)[-1]).lower()
    if slug:
        return f"slug:{slug}"
    if urn:
        return f"urn:{urn.strip().lower()}"
    return f"name:{re.sub(r'[^a-z0-9]+', '-', name.strip().lower()).strip('-')}"


def _dedupe(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """One human, one row. The same person arrives by slug and by member URN."""
    seen: set = set()
    out: List[Dict[str, str]] = []
    for r in rows:
        key = identity_key(r.get("public_url", ""), r.get("urn", ""), r.get("name", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _norm(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (key or "").lower())


_ARCHIVE_ALIASES = {
    "name": ("from", "inviterfirstname", "invitername", "name"),
    "public_url": ("inviterprofileurl", "profileurl", "publicurl", "url"),
    "note": ("message", "note"),
    "sent_at": ("sentat", "senttime", "date"),
    "direction": ("direction",),
}


def _iso(value: str) -> str:
    """Normalize whatever LinkedIn stamped into ISO. The ENGINE must not guess."""
    text = (value or "").strip()
    if not text:
        return ""
    for fmt in ("%Y-%m-%d", "%m/%d/%y, %I:%M %p", "%m/%d/%Y, %I:%M %p",
                "%m/%d/%y", "%m/%d/%Y", "%d %b %Y", "%b %d, %Y",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S UTC"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    # Relative stamps only ever arrive from the live DOM ("1 month ago").
    m = re.match(r"(\d+)\s+(day|week|month|year)s?\s+ago", text, re.I)
    if m:
        n, unit = int(m.group(1)), m.group(2).lower()
        days = {"day": 1, "week": 7, "month": 30, "year": 365}[unit] * n
        return (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date().isoformat()
    except ValueError:
        return ""


def _write_rows(li_dir: Path, rows: List[Dict[str, str]], rung: int, dry_run: bool) -> Path:
    li_dir.mkdir(parents=True, exist_ok=True)
    path = li_dir / "invitations.csv"
    if dry_run:
        return path
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CANONICAL_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in CANONICAL_FIELDS})
    os.replace(tmp, path)  # atomic: a half-written queue is worse than a stale one
    (li_dir / ".ingest.json").write_text(json.dumps({
        "rung": rung, "source": RUNGS[rung], "rows": len(rows),
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }, indent=2) + "\n", encoding="utf-8")
    return path


def _state(li_dir: Path) -> Dict[str, Any]:
    try:
        return json.loads((li_dir / ".ingest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# --------------------------------------------------------------------------- #
# Rung 1 — cache
# --------------------------------------------------------------------------- #

def rung1_cache(li_dir: Path, max_age_hours: float) -> Optional[Tuple[List[Dict[str, str]], str]]:
    path = li_dir / "invitations.csv"
    if not path.is_file():
        return None
    age_h = (time.time() - path.stat().st_mtime) / 3600.0
    if age_h > max_age_hours:
        return None
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    # Count what will actually be TRIAGED, not raw file lines — otherwise this
    # rung reports 14 while the card reports 11 and the difference looks like a
    # bug rather than the sent/companyFollow rows being correctly dropped.
    triageable = [r for r in rows
                  if (r.get("direction") or "received").lower().startswith("receiv")
                  and (r.get("invitation_type") or "connect").lower()
                  in ("connect", "connection", "invitation", "")]
    prior = _state(li_dir)
    return _dedupe(triageable), prior.get("source", RUNGS[1])


# --------------------------------------------------------------------------- #
# Rung 2 — LinkedIn's own archive export
# --------------------------------------------------------------------------- #

def parse_archive_messages(zip_path: Path) -> str:
    """Pull messages.csv out of the export, verbatim.

    The engine already understands LinkedIn's own column names, so this is a
    passthrough rather than a re-mapping — and passing the raw file through means
    a change in their schema surfaces as an unrecognised column rather than as
    silently dropped messages.

    Returns "" when the archive has no messages (the user did not tick that box).
    """
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist()
                 if n.lower().endswith(".csv")
                 and ("message" in n.lower() or "conversation" in n.lower())]
        if not names:
            return ""
        return zf.read(names[0]).decode("utf-8-sig", "replace")


def parse_archive(zip_path: Path) -> List[Dict[str, str]]:
    """Read Invitations.csv out of a "Get a copy of your data" zip.

    LinkedIn ships invitee/inviter names, the profile URL, the date sent, and the
    invitation MESSAGE — everything the rubric scores. It does NOT ship headline,
    mutual-connection count, or network size, so those stay blank. Blank means
    "we did not look" and the grader treats it that way. Missing is not zero.
    """
    rows: List[Dict[str, str]] = []
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if "invitation" in n.lower() and n.lower().endswith(".csv")]
        if not names:
            raise FileNotFoundError(
                f"No Invitations.csv inside {zip_path.name}. The archive was probably "
                "requested without the Invitations category ticked."
            )
        for name in names:
            text = zf.read(name).decode("utf-8-sig", "replace")
            for raw in csv.DictReader(io.StringIO(text)):
                row = {_norm(k): (v or "").strip() for k, v in raw.items()}
                direction = row.get("direction", "").upper()
                if direction and not direction.startswith("INCOMING"):
                    continue  # invitations WE sent are a different queue
                out: Dict[str, str] = {"direction": "received", "invitation_type": "connect"}
                for field, aliases in _ARCHIVE_ALIASES.items():
                    for alias in aliases:
                        if row.get(_norm(alias)):
                            out[field] = row[_norm(alias)]
                            break
                out["sent_at"] = _iso(out.get("sent_at", ""))
                out["direction"] = "received"  # the alias loop may have copied INCOMING
                if out.get("name") or out.get("public_url"):
                    rows.append(out)
    return rows


def _request_archive(drv: browser.Driver) -> str:
    """Tick Connections + Invitations + Messages and submit. Returns a status word."""
    drv.goto(DOWNLOAD_MY_DATA)
    time.sleep(4)
    return drv.evaluate(r"""
    (() => {
      const txt = el => (el.innerText || el.textContent || '').toLowerCase();
      // A ready archive short-circuits the whole request.
      const dl = Array.from(document.querySelectorAll('a,button'))
        .find(e => /download archive/i.test(txt(e)));
      if (dl) return 'ready';
      const pick = Array.from(document.querySelectorAll('input[type=radio],input[type=checkbox]'))
        .find(i => /want something in particular|specific/i.test(
          txt(i.closest('label') || i.parentElement || document.body)));
      if (pick && !pick.checked) pick.click();
      let ticked = 0;
      for (const box of document.querySelectorAll('input[type=checkbox]')) {
        const label = txt(box.closest('label') || box.parentElement || {});
        if (/(invitation|connection|message)/.test(label) && !box.checked) { box.click(); ticked++; }
      }
      const submit = Array.from(document.querySelectorAll('button'))
        .find(b => /request archive/i.test(txt(b)) && !b.disabled);
      if (!submit) return ticked ? 'ticked-no-submit' : 'no-controls';
      submit.click();
      return 'requested';
    })()
    """) or "unknown"


def _download_archive(drv: browser.Driver, dest: Path) -> Optional[Path]:
    """Fetch the ready archive from inside the page so the session cookie applies."""
    href = drv.evaluate(r"""
    (() => {
      const a = Array.from(document.querySelectorAll('a'))
        .find(e => /download archive/i.test(e.innerText || '') && e.href);
      return a ? a.href : null;
    })()
    """)
    if not href:
        return None
    b64 = drv.evaluate(
        "(async () => { const r = await fetch(%s, {credentials:'include'});"
        " if (!r.ok) return null; const b = await r.arrayBuffer();"
        " let s=''; const u=new Uint8Array(b);"
        " for (let i=0;i<u.length;i+=8192) s+=String.fromCharCode.apply(null,u.subarray(i,i+8192));"
        " return btoa(s); })()" % json.dumps(href)
    )
    if not b64:
        return None
    import base64
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(base64.b64decode(b64))
    return dest


def _save_messages(li_dir: Path, text: str, dry_run: bool) -> int:
    """Write messages.csv alongside invitations.csv. Returns the row count."""
    if not text.strip() or dry_run:
        return 0
    li_dir.mkdir(parents=True, exist_ok=True)
    path = li_dir / "messages.csv"
    tmp = path.with_suffix(".csv.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return max(0, len(text.strip().splitlines()) - 1)


def rung2_archive(li_dir: Path, *, zip_path: Optional[Path], wait_minutes: float,
                  prefer: str) -> Optional[List[Dict[str, str]]]:
    if zip_path:
        # The export carries messages too, and dropping them meant the DM half of
        # the product had no data on its primary path.
        globals()["_LAST_MESSAGE_ROWS"] = _save_messages(
            li_dir, parse_archive_messages(zip_path), dry_run=False)
        return parse_archive(zip_path)
    drv = browser.open_driver(prefer)          # raises -> caller falls a rung
    try:
        status = _request_archive(drv)
        if status in ("no-controls", "ticked-no-submit"):
            raise browser.BrowserUnavailable(
                f"Archive request page did not behave as expected ({status}). "
                "Record what changed in references/dom-notes.md."
            )
        deadline = time.time() + wait_minutes * 60
        dest = li_dir / "archive" / "LinkedInDataExport.zip"
        while time.time() < deadline:
            got = _download_archive(drv, dest)
            if got:
                globals()["_LAST_MESSAGE_ROWS"] = _save_messages(
                    li_dir, parse_archive_messages(got), dry_run=False)
                return parse_archive(got)
            time.sleep(20)
            drv.goto(DOWNLOAD_MY_DATA)
            time.sleep(4)
        raise browser.BrowserUnavailable(
            f"Archive still not ready after {wait_minutes:.0f}m. LinkedIn says specific "
            "categories arrive 'within minutes' but the full archive can take 24h. "
            "Re-run later, or pass --from-archive once the mail lands."
        )
    finally:
        drv.close()


# --------------------------------------------------------------------------- #
# Rung 3 — live invitation-manager DOM
# --------------------------------------------------------------------------- #

_SCRAPE_JS = r"""
(() => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const out = [];
  const accepts = Array.from(document.querySelectorAll('button, a'))
    .filter(b => (b.getAttribute('aria-label') || '').startsWith('Accept '));
  for (const btn of accepts) {
    const aria = btn.getAttribute('aria-label') || '';
    // "Accept <Name>'s invitation" — LinkedIn uses a CURLY apostrophe here.
    const m = aria.match(/^Accept (.+?)[’']s invitation$/);
    const card = btn.closest('li, article, div[data-view-name], .invitation-card') || btn.parentElement;
    const text = norm(card ? card.innerText : '');
    const link = card ? card.querySelector('a[href*="/in/"]') : null;
    const mutual = text.match(/(\d[\d,]*)\s+mutual connection/i);
    out.push({
      name: m ? m[1] : norm(aria.replace(/^Accept\s+/, '')),
      public_url: link ? link.href.split('?')[0] : '',
      // A premium "Follows you" card renders Accept as an <a>, not a <button>,
      // and no click method fires its handler. Carry the tag so the caller can
      // route those rows instead of silently failing on them.
      accept_tag: btn.tagName,
      headline: norm((card && card.querySelector('p, .t-12, [class*="subtitle"]') || {}).innerText || ''),
      note: norm((card && card.querySelector('[class*="message"], blockquote') || {}).innerText || ''),
      mutual_connections: mutual ? mutual[1].replace(/,/g, '') : '',
      sent_at_relative: (text.match(/(\d+\s+(?:day|week|month|year)s?\s+ago)/i) || [])[1] || ''
    });
  }
  return out;
})()
"""


def rung3_live(li_dir: Path, *, limit: int, prefer: str) -> Optional[List[Dict[str, str]]]:
    if limit > LIVE_READ_CAP:
        raise browser.BrowserUnavailable(
            f"refusing to read {limit} invitations live — that is roughly "
            f"{limit // 10} automated page loads against a signed-in session, and "
            "bulk activity like that is what gets LinkedIn accounts restricted. "
            "Use the data export instead (Settings -> Data Privacy -> Get a copy "
            "of your data -> Invitations); it returns the whole queue in one "
            f"download. Pass --limit {LIVE_READ_CAP} or less to read live anyway.")
    drv = browser.open_driver(prefer)
    try:
        rows: List[Dict[str, str]] = []
        seen: set = set()
        stalled = 0
        while len(rows) < limit and stalled < 2:
            # The manager mounts ~10 cards and scrolling does NOT load more, so
            # re-navigate rather than scroll. See references/dom-notes.md.
            drv.goto(INVITATION_MANAGER)
            time.sleep(3)
            batch = drv.evaluate(_SCRAPE_JS) or []
            fresh = 0
            for item in batch:
                key = item.get("public_url") or item.get("name")
                if not key or key in seen:
                    continue
                seen.add(key)
                fresh += 1
                rows.append({
                    "name": item.get("name", ""),
                    "public_url": item.get("public_url", ""),
                    "headline": item.get("headline", ""),
                    "note": item.get("note", ""),
                    "mutual_connections": item.get("mutual_connections", ""),
                    "sent_at": _iso(item.get("sent_at_relative", "")),
                    "invitation_type": "connect",
                    "direction": "received",
                })
            stalled = stalled + 1 if fresh == 0 else 0
        if not rows:
            raise browser.BrowserUnavailable(
                "Invitation manager returned no Accept controls. Either the queue is "
                "genuinely empty or the session is logged out — those are different "
                "answers and this rung will not guess between them."
            )
        return rows
    finally:
        drv.close()


# --------------------------------------------------------------------------- #
# Rung 4 — HubSpot mirror
# --------------------------------------------------------------------------- #

def rung4_hubspot(li_dir: Path, data_dir: Path) -> Optional[List[Dict[str, str]]]:
    """Partial mirror from the linkedin_* contact properties.

    Only ever a SUBSET: HubSpot knows the people who already reached the CRM, so
    a count from here is not the size of the queue. The card labels it
    `hubspot-mirror` for exactly that reason. Note the heyreach_* family is empty
    portal-wide — do not read it and do not report from it.
    """
    rows: List[Dict[str, str]] = []
    for path in sorted((data_dir / "hubspot").glob("*.csv")) if (data_dir / "hubspot").is_dir() else []:
        try:
            with path.open(encoding="utf-8-sig", newline="") as fh:
                for raw in csv.DictReader(fh):
                    row = {_norm(k): (v or "").strip() for k, v in raw.items()}
                    status = row.get("linkedininboundinvitationstatus", "")
                    if status.lower() != "pending":
                        continue
                    name = " ".join(p for p in (row.get("firstname", ""), row.get("lastname", "")) if p)
                    rows.append({
                        "name": name or row.get("email", ""),
                        "public_url": row.get("hslinkedinurl", "") or row.get("linkedinurl", ""),
                        "urn": row.get("linkedinidentitykeyalt", ""),
                        "headline": row.get("jobtitle", ""),
                        "company": row.get("company", ""),
                        "note": row.get("linkedinconnectionrequestnote", ""),
                        "sent_at": _iso(row.get("linkedininboundinvitationreceivedat", "")),
                        "invitation_type": "connect", "direction": "received",
                    })
        except (OSError, ValueError):
            continue
    return rows or None


# --------------------------------------------------------------------------- #
# Ladder
# --------------------------------------------------------------------------- #

def ingest(profile: Path, *, only_rung: Optional[int] = None, zip_path: Optional[Path] = None,
           max_age_hours: float = 20.0, limit: int = LIVE_READ_CAP, wait_minutes: float = 10.0,
           prefer: str = "auto", dry_run: bool = False) -> Dict[str, Any]:
    li_dir, data_dir = profile / "data" / "linkedin", profile / "data"
    attempts: List[Dict[str, str]] = []
    if only_rung:
        wanted = [only_rung]
    elif zip_path:
        # An explicitly named archive is an instruction, not a hint. Falling
        # through to the cache here silently ignored the file the caller just
        # handed us and reported stale data as if it were the import.
        wanted = [2, 3, 4]
    else:
        wanted = [1, 2, 3, 4]

    for rung in wanted:
        try:
            if rung == 1:
                got = rung1_cache(li_dir, max_age_hours)
                if got:
                    rows, src = got
                    return {"ok": True, "rung": 1, "source": src, "rows": len(rows),
                            "path": str(li_dir / "invitations.csv"), "reused_cache": True,
                            "attempts": attempts}
                attempts.append({"rung": "1 cache", "why": "no fresh invitations.csv"})
                continue
            rows = {2: lambda: rung2_archive(li_dir, zip_path=zip_path,
                                             wait_minutes=wait_minutes, prefer=prefer),
                    3: lambda: rung3_live(li_dir, limit=limit, prefer=prefer),
                    4: lambda: rung4_hubspot(li_dir, data_dir)}[rung]()
            rows = _dedupe(rows)
            if rows:
                path = _write_rows(li_dir, rows, rung, dry_run)
                result = {"ok": True, "rung": rung, "source": RUNGS[rung],
                          "rows": len(rows), "path": str(path), "dry_run": dry_run,
                          "attempts": attempts}
                if _LAST_MESSAGE_ROWS:
                    result["message_rows"] = _LAST_MESSAGE_ROWS
                return result
            attempts.append({"rung": f"{rung} {RUNGS[rung]}", "why": "returned no rows"})
        except Exception as exc:  # noqa: BLE001 — a failed rung must not end the ladder
            attempts.append({"rung": f"{rung} {RUNGS[rung]}", "why": str(exc)[:300]})

    # Rung 5. Say so. Never fabricate a population, and never leave a stale file
    # looking fresh — an empty report is a real answer, a wrong one is not.
    return {"ok": False, "rung": 5, "source": RUNGS[5], "rows": 0,
            "attempts": attempts,
            "remedy": "No rung reached LinkedIn. Either sign in to the browser profile this "
                      "runs against, or download the archive by hand and pass --from-archive."}


def doctor(profile: Path) -> Tuple[Dict[str, Any], int]:
    """Which rungs can run right now, and how stale the queue is."""
    li = profile / "data" / "linkedin"
    state = _state(li)
    drivers = browser.available_drivers()
    rungs: List[int] = []
    csvs = sorted(li.glob("*.csv")) if li.is_dir() else []
    age_h = ((time.time() - max(p.stat().st_mtime for p in csvs)) / 3600.0) if csvs else None
    if csvs:
        rungs.append(1)
    if drivers:
        rungs += [2, 3]
    if (profile / "data" / "hubspot").is_dir():
        rungs.append(4)
    results = {
        "drivers": drivers,
        "rungs_reachable": sorted(set(rungs)),
        "queue_rows": state.get("rows"),
        "queue_age_hours": round(age_h, 1) if age_h is not None else None,
        "last_ingest": state or None,
        "remedy": None if rungs else (
            "No rung can run. Install ego-browser, or start Chrome with "
            "--remote-debugging-port=9222 on the profile signed in to LinkedIn, "
            "or pass a downloaded export with --from-archive."),
    }
    return results, (cc.OK if rungs else cc.UNREACHABLE)


_EXIT_FOR_ATTEMPTS = (
    ("rate", cc.RATE_LIMITED),
    ("sign in", cc.UNREACHABLE),
    ("logged out", cc.UNREACHABLE),
    ("no browser", cc.UNREACHABLE),
    ("not on path", cc.UNREACHABLE),
    ("devtools", cc.UNREACHABLE),
)


def _exit_for(res: Dict[str, Any]) -> int:
    """Map a failed ladder to a code a scheduler can branch on."""
    if res.get("ok"):
        return cc.OK
    blob = " ".join(a.get("why", "") for a in res.get("attempts", [])).lower()
    for needle, code in _EXIT_FOR_ATTEMPTS:
        if needle in blob:
            return code
    return cc.UNREACHABLE


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="LinkedIn inbound ingest (fallback ladder)",
        epilog="Exit codes: " + " · ".join(f"{k}={v}" for k, v in cc.EXIT_MEANING.items()))
    ap.add_argument("--profile-dir", default=os.environ.get("ERNEST_PROFILE_DIR", os.getcwd()))
    ap.add_argument("--from-archive", dest="zip_path", help="a downloaded LinkedIn export .zip")
    ap.add_argument("--rung", type=int, choices=[1, 2, 3, 4], help="force one rung")
    ap.add_argument("--max-age-hours", type=float, default=20.0)
    ap.add_argument("--limit", type=int, default=LIVE_READ_CAP,
                    help=f"max invitations to read live (cap {LIVE_READ_CAP}; "
                         "use the data export for bulk)")
    ap.add_argument("--wait-minutes", type=float, default=10.0, help="how long to wait for the archive")
    ap.add_argument("--prefer", choices=["auto", "ego", "chrome"], default="auto")
    ap.add_argument("--doctor", action="store_true", help="what is reachable right now")
    ap.add_argument("--status", action="store_true", help="alias for --doctor")
    ap.add_argument("--save-profile", metavar="NAME",
                    help="save the current flags as a named profile and exit")
    ap.add_argument("--feedback", metavar="NOTE",
                    help="record one line about what surprised you, then exit")
    cc.add_common_flags(ap)
    args = ap.parse_args(argv)
    cc.resolve_common(args)
    profile = Path(args.profile_dir).resolve()

    if args.feedback:
        path = cc.record_feedback(profile, args.feedback)
        return cc.emit(cc.envelope({"recorded": str(path)}, source="local"),
                       as_json=args.json, compact=args.compact, sink=args.deliver,
                       human=f"Noted. {path}")

    defaults = {"rung": None, "max_age_hours": 20.0, "limit": LIVE_READ_CAP, "wait_minutes": 10.0,
                "prefer": "auto", "zip_path": None, "dry_run": False}
    err = cc.apply_profile(args, profile, defaults)
    if err:
        print(f"ingest: {err}", file=sys.stderr)
        return cc.CONFIG

    if args.save_profile:
        cc.save_profile(profile, args.save_profile,
                        {k: getattr(args, k) for k in defaults})
        return cc.emit(cc.envelope({"saved": args.save_profile}, source="local"),
                       as_json=args.json, compact=args.compact, sink=args.deliver,
                       human=f"Saved profile {args.save_profile!r}.")

    if args.doctor or args.status:
        results, code = doctor(profile)
        human = (f"drivers: {results['drivers'] or 'none'}\n"
                 f"rungs reachable: {results['rungs_reachable'] or 'none'}\n"
                 f"queue: {results['queue_rows']} row(s), "
                 f"{results['queue_age_hours']}h old\n"
                 + (f"remedy: {results['remedy']}" if results["remedy"] else ""))
        cc.emit(cc.envelope(results, source="local", reason="doctor"),
                as_json=args.json, compact=args.compact, sink=args.deliver, human=human)
        return code

    res = ingest(profile, only_rung=args.rung,
                 zip_path=Path(args.zip_path).expanduser() if args.zip_path else None,
                 max_age_hours=args.max_age_hours, limit=args.limit,
                 wait_minutes=args.wait_minutes, prefer=args.prefer, dry_run=args.dry_run)
    lines = [f"  rung {a['rung']}: {a['why']}" for a in res["attempts"]]
    if res["ok"]:
        msgs = res.get("message_rows") or 0
        lines.append(f"Ingest: rung {res['rung']} ({res['source']}) — {res['rows']} invitation(s)"
                     + (f", {msgs} message row(s)" if msgs else "")
                     + (" [dry run, nothing written]" if res.get("dry_run") else f" -> {res['path']}"))
        if not msgs and res["rung"] == 2:
            lines.append("  note: no messages in that archive — tick Messages in the "
                         "export request if you want the DM report too.")
    else:
        lines.append(f"Ingest: UNAVAILABLE. {res['remedy']}")
    cc.emit(cc.envelope(res, source=res["source"], rung=res["rung"],
                        reason="" if res["ok"] else res.get("remedy", "")),
            as_json=args.json, compact=args.compact, sink=args.deliver,
            human="\n".join(lines))
    return _exit_for(res)


if __name__ == "__main__":
    raise SystemExit(main())
