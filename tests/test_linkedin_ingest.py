#!/usr/bin/env python3
"""The ingest ladder: honest provenance, honest counts, honest failure.

  1. The adapter's identity_key copy agrees with the engine's (it is duplicated
     on purpose — the adapter must run standalone — so it needs a leash).
  2. The archive parser drops OUTGOING and keeps the invitation note.
  3. Counts agree with what the engine will actually triage.
  4. Dates are normalized by the ADAPTER; the engine never guesses.
  5. Missing counts stay blank through the whole pipe — never 0.
  6. A dead ladder returns rung 5 and fabricates nothing.
  7. Exit codes are the documented ones.
"""
from __future__ import annotations

import csv
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "adapters" / "linkedin"))

import cli_common as cc  # noqa: E402
import ingest  # noqa: E402
from ernest import config, sources  # noqa: E402
from ernest.grading import identity_key as engine_key  # noqa: E402

FAILURES = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global FAILURES
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES += 1


def _archive(path: Path) -> None:
    rows = [
        {"From": "Priya Raman", "To": "CEO", "Sent At": "6/02/26, 9:14 AM",
         "Message": "We're an AI audio series studio. Do you do volume pricing?",
         "Direction": "INCOMING",
         "inviterProfileUrl": "https://www.linkedin.com/in/priya-raman-sample"},
        {"From": "Priya Raman", "To": "CEO", "Sent At": "6/02/26, 9:14 AM", "Message": "",
         "Direction": "INCOMING",
         "inviterProfileUrl": "https://www.linkedin.com/in/priya-raman-sample?trk=dup"},
        {"From": "CEO", "To": "Someone", "Sent At": "5/01/26, 1:00 PM", "Message": "",
         "Direction": "OUTGOING",
         "inviterProfileUrl": "https://www.linkedin.com/in/outbound-sample"},
    ]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Invitations.csv", buf.getvalue())
        zf.writestr("Connections.csv", "First Name,Last Name,URL\nA,B,https://x\n")


def main() -> int:
    # 1. The duplicated identity_key must not drift from the engine's.
    for url, urn, name in (
        ("https://www.linkedin.com/in/jane-doe/", "ACoAA1", ""),
        ("https://www.linkedin.com/in/jane-doe?trk=x", "", ""),
        ("", "ACoAA1", ""),
        ("", "", "Jane  Doe"),
        ("https://www.linkedin.com/company/acme", "", "Acme"),
    ):
        check(f"identity_key agrees for {url or urn or name!r}",
              ingest.identity_key(url, urn, name) == engine_key(url, urn, name),
              f"{ingest.identity_key(url, urn, name)} vs {engine_key(url, urn, name)}")

    # 4. Date normalization is the adapter's job.
    for raw, want in (("6/02/26, 9:14 AM", "2026-06-02"), ("2026-06-02", "2026-06-02"),
                      ("Jun 2, 2026", "2026-06-02"), ("not a date", "")):
        check(f"_iso({raw!r}) -> {want!r}", ingest._iso(raw) == want, ingest._iso(raw))

    with tempfile.TemporaryDirectory() as tmp:
        profile = Path(tmp) / "p"
        (profile / "data" / "grading").mkdir(parents=True)
        # Only the LinkedIn rubric is required here. Copying whichever others
        # happen to exist keeps this runnable inside the standalone bundle,
        # which ships the LinkedIn rubric alone.
        for src in (ROOT / "data" / "grading").glob("*-rubric.json"):
            (profile / "data" / "grading" / src.name).write_text(
                src.read_text(encoding="utf-8"), encoding="utf-8")
        zip_path = profile / "export.zip"
        _archive(zip_path)

        # 2 + 3. Parse, drop OUTGOING, dedupe, keep the note.
        rows = ingest._dedupe(ingest.parse_archive(zip_path))
        check("OUTGOING rows are dropped", len(rows) == 1, str(len(rows)))
        check("the invitation note survives",
              "volume pricing" in rows[0].get("note", ""), rows[0].get("note", ""))
        check("direction is normalized to received", rows[0]["direction"] == "received")

        res = ingest.ingest(profile, zip_path=zip_path)
        check("rung 2 is reported, not guessed",
              res["rung"] == 2 and res["source"] == "linkedin-archive", str(res))
        check("adapter row count matches what it wrote", res["rows"] == 1, str(res["rows"]))

        # 3 + 5. The engine sees the same population, with blanks still blank.
        import os
        os.environ["ERNEST_PROFILE_DIR"] = str(profile)
        cfg = config.load()
        invs = sources.load_invitations(cfg)
        check("engine population matches the adapter's count", len(invs) == res["rows"],
              f"{len(invs)} vs {res['rows']}")
        check("provenance rides through to the engine",
              invs[0].source == "linkedin-archive", invs[0].source)
        check("missing mutual count stays None, never 0",
              invs[0].mutual_connections is None, repr(invs[0].mutual_connections))
        check("missing network size stays None, never 0",
              invs[0].connections is None, repr(invs[0].connections))

        # 6. A dead ladder fabricates nothing.
        empty = Path(tmp) / "empty"
        empty.mkdir()
        os.environ["ERNEST_PROFILE_DIR"] = str(empty)
        dead = ingest.ingest(empty, only_rung=4)
        check("a dead ladder reports rung 5", dead["rung"] == 5, str(dead["rung"]))
        check("a dead ladder invents no rows", dead["rows"] == 0)
        check("a dead ladder says why", bool(dead.get("remedy")))
        check("a dead ladder writes no file",
              not (empty / "data" / "linkedin" / "invitations.csv").exists())

        # 7. Documented exit codes.
        check("unknown profile -> CONFIG(10)",
              ingest.main(["--profile-dir", str(profile), "--profile", "nope"]) == cc.CONFIG)
        check("successful ingest -> OK(0)",
              ingest.main(["--profile-dir", str(profile), "--from-archive", str(zip_path),
                           "--agent", "--deliver", f"file:{profile}/out.json"]) == cc.OK)
        check("the delivered file is a provenance envelope",
              set(json.loads((profile / "out.json").read_text())) == {"meta", "results"})
        check("dead ladder -> UNREACHABLE(4)",
              ingest.main(["--profile-dir", str(empty), "--rung", "4", "--agent",
                           "--deliver", f"file:{empty}/out.json"]) == cc.UNREACHABLE)

    if FAILURES:
        print(f"FAIL - LinkedIn ingest ({FAILURES} failure(s))")
        return 1
    print("PASS - LinkedIn ingest: identity parity, provenance, blanks, honest failure, exit codes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
