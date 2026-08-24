#!/usr/bin/env python3
"""Real-export nastiness: malformed, hostile, and ambiguous input.

Every case here came from throwing generated garbage at the pipeline rather than
from imagining what might go wrong. The three that actually broke it — and would
have corrupted a real export — are marked.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILURES = 0
HEAD = ("name,public_url,urn,headline,company,location,note,sent_at,"
        "mutual_connections,connections,invitation_type,direction\n")
MHEAD = ("CONVERSATION ID,CONVERSATION TITLE,FROM,SENDER PROFILE URL,TO,"
         "RECIPIENT PROFILE URLS,DATE,SUBJECT,CONTENT,FOLDER\n")


def check(label: str, cond: bool, detail: str = "") -> None:
    global FAILURES
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES += 1


def _profile(inv: str = HEAD, msg: str = MHEAD, persona: str = "Alex Mashrabov") -> Path:
    d = Path(tempfile.mkdtemp())
    (d / "data" / "linkedin").mkdir(parents=True)
    (d / "data" / "grading").mkdir(parents=True)
    (d / "memory").mkdir(parents=True)
    for f in (ROOT / "data" / "grading").glob("*.json"):
        shutil.copy(f, d / "data" / "grading" / f.name)
    (d / "memory" / "ceo-persona.md").write_text(f"# CEO Persona\n\n- Name: {persona}\n",
                                                 encoding="utf-8")
    (d / "data" / "linkedin" / "invitations.csv").write_text(inv, encoding="utf-8", newline="")
    (d / "data" / "linkedin" / "messages.csv").write_text(msg, encoding="utf-8", newline="")
    os.environ.update(ERNEST_PROFILE_DIR=str(d), ERNEST_LOCAL_VAULT=str(d / "vault"),
                      ERNEST_TODAY="2026-08-24")
    for m in [k for k in sys.modules if k.startswith("ernest")]:
        del sys.modules[m]
    return d


def _load(inv=HEAD, msg=MHEAD, persona="Alex Mashrabov"):
    d = _profile(inv, msg, persona)
    from ernest import config, sources          # noqa: E402
    cfg = config.load()
    return d, sources.load_invitations(cfg), sources.load_conversations(cfg)


def main() -> int:
    # --- BROKE IT: two different people, one display name, no profile URL -----
    # A name is not an identifier. Deduping on it silently deleted a real person.
    _, invs, _ = _load(HEAD +
                       'John Smith,,,Head of Growth,Acme,,"note A",2026-08-01,5,900,connect,received\n'
                       'John Smith,,,Founder,Zenith,,"note B",2026-08-02,7,800,connect,received\n')
    check("two people sharing a name are both kept", len(invs) == 2, f"kept {len(invs)} of 2")
    check("...and stay distinguishable",
          {i.headline for i in invs} == {"Head of Growth", "Founder"})

    # A real identifier still dedupes.
    _, invs, _ = _load(HEAD +
                       'A,https://x.com/in/same,,H1,,,n,2026-08-01,1,10,connect,received\n'
                       'A,https://x.com/in/same?trk=z,,H2,,,n,2026-08-02,1,10,connect,received\n')
    check("one person under two URL forms collapses", len(invs) == 1, f"kept {len(invs)}")

    # --- BROKE IT: negative counts scored as an extreme, not as unknown -------
    _, invs, _ = _load(HEAD +
                       'Neg,https://x.com/in/neg,,H,,,n,2026-08-01,-5,-99,connect,received\n')
    check("a negative count reads as unknown, not as evidence",
          invs[0].mutual_connections is None and invs[0].connections is None,
          f"{invs[0].mutual_connections}/{invs[0].connections}")

    # --- BROKE IT: a group thread was attributed to whoever wrote first -------
    _, _, convos = _load(msg=MHEAD +
                         'g1,,Alice,https://x.com/in/alice,Alex Mashrabov,https://x.com/in/alex,2026-08-01,,"a",INBOX\n'
                         'g1,,Zoe,https://x.com/in/zoe,Alex Mashrabov,https://x.com/in/alex,2026-08-02,,"z",INBOX\n'
                         'g1,,Zoe,https://x.com/in/zoe,Alex Mashrabov,https://x.com/in/alex,2026-08-03,,"z2",INBOX\n')
    g = convos[0]
    check("a group thread is recognised", g.is_group, str(g.participants))
    check("...everyone is named", set(g.participants) == {"Alice", "Zoe"}, str(g.participants))
    check("...and it is attributed to whoever actually drove it",
          g.counterparty == "Zoe", g.counterparty)

    # --- input that must simply not explode ---------------------------------
    for label, inv, msg in [
        ("a completely empty file", "", ""),
        ("headers with no rows", HEAD, MHEAD),
        ("a BOM and CRLF line endings",
         "﻿" + HEAD.replace("\n", "\r\n") +
         'A,https://x.com/in/a,,H,,,n,2026-08-01,1,10,connect,received\r\n', MHEAD),
        ("commas and quotes inside a note", HEAD +
         'B,https://x.com/in/b,,"Head, of Growth",,,"He said ""hi"", then left",2026-08-01,1,10,connect,received\n', MHEAD),
        ("a newline inside a note", HEAD +
         'C,https://x.com/in/c,,H,,,"line one\nline two",2026-08-01,1,10,connect,received\n', MHEAD),
        ("non-latin names and emoji", HEAD +
         'Юрий Петров,https://x.com/in/yuri,,Основатель,,,"Здравствуйте",2026-08-01,3,100,connect,received\n'
         '李伟,https://x.com/in/liwei,,创始人,,,"你好",2026-08-01,3,100,connect,received\n'
         '🚀 Rocket,https://x.com/in/rocket,,Founder,,,"hey 👋",2026-08-01,3,100,connect,received\n', MHEAD),
        ("a 60,000-character note", HEAD +
         f'D,https://x.com/in/d,,H,,,"{"spam " * 12000}",2026-08-01,0,5,connect,received\n', MHEAD),
        ("unparseable and impossible dates", HEAD +
         'E,https://x.com/in/e,,H,,,n,not-a-date,1,10,connect,received\n'
         'F,https://x.com/in/f,,H,,,n,9999-99-99,1,10,connect,received\n', MHEAD),
        ("columns missing entirely", "name,note\nJ,hello\n", MHEAD),
        ("unknown extra columns", HEAD.rstrip("\n") + ",weird\n" +
         'K,https://x.com/in/k,,H,,,n,2026-08-01,1,10,connect,received,x\n', MHEAD),
        ("a URL with no name", HEAD +
         ',https://x.com/in/nameless,,H,,,n,2026-08-01,1,10,connect,received\n', MHEAD),
        ("a message with an empty body", HEAD, MHEAD +
         'c1,,Alice,https://x.com/in/alice,Alex Mashrabov,https://x.com/in/alex,2026-08-01,,,INBOX\n'),
        ("a thread with only outbound messages", HEAD, MHEAD +
         'c1,,Alex Mashrabov,https://x.com/in/alex,Alice,https://x.com/in/alice,2026-08-01,,"you there?",INBOX\n'),
        ("a message from the owner to themselves", HEAD, MHEAD +
         'c1,,Alex Mashrabov,https://x.com/in/alex,Alex Mashrabov,https://x.com/in/alex,2026-08-01,,"note to self",INBOX\n'),
    ]:
        try:
            d = _profile(inv, msg)
            from ernest import config, grade_run   # noqa: E402
            grade_run.run(config.load(), b2b=False, talent=False,
                          linkedin=True, linkedin_dms=True)
            ok, detail = True, ""
        except Exception as exc:                    # noqa: BLE001
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        finally:
            shutil.rmtree(d, ignore_errors=True)
        check(f"survives {label}", ok, detail)

    # --- BROKE IT: a configured name that matches nobody in the export -------
    # The seeded persona said one name, the export used another. Nothing matched,
    # so every message read as inbound and the owner's own replies came back as
    # unanswered mail — a completely inverted inbox that still looked like a
    # normal report. This is the most damaging failure in the module.
    _, _, convos = _load(msg=MHEAD +
                         'c1,,Real Owner,https://x.com/in/owner,Alice,https://x.com/in/alice,2026-08-01,,"hi",INBOX\n'
                         'c1,,Alice,https://x.com/in/alice,Real Owner,https://x.com/in/owner,2026-08-02,,"hello back",INBOX\n'
                         'c2,,Real Owner,https://x.com/in/owner,Bob,https://x.com/in/bob,2026-08-03,,"hey",INBOX\n',
                         persona="Someone Who Is Not In This Export")
    import ernest.sources as _s          # after _load: it re-imports the package
    names = {c.counterparty for c in convos}
    check("a persona name matching nobody is not trusted",
          "Real Owner" not in names, str(names))
    owner, how = _s.last_owner()
    check("...the real owner is inferred instead", owner == "real owner", owner)
    check("...and the report can say how it decided",
          "inferred" in how, how)

    # A name that DOES appear is trusted, and reported as configured.
    _, _, convos = _load(msg=MHEAD +
                         'c1,,Alice,https://x.com/in/alice,Real Owner,https://x.com/in/owner,2026-08-01,,"hi",INBOX\n'
                         'c1,,Real Owner,https://x.com/in/owner,Alice,https://x.com/in/alice,2026-08-02,,"reply",INBOX\n',
                         persona="Real Owner")
    import ernest.sources as _s2
    owner, how = _s2.last_owner()
    check("a persona name present in the export is trusted",
          owner == "real owner" and "persona" in how, f"{owner} / {how}")
    check("...and our own reply is not counted as owed",
          convos and not convos[0].owed, str([c.owed for c in convos]))

    # --- the owner is not simply the loudest sender -------------------------
    _, _, convos = _load(msg=MHEAD +
                         'c1,,Alice,https://x.com/in/alice,Bob Owner,https://x.com/in/bob,2026-08-01,,"hi",INBOX\n'
                         'c2,,Carol,https://x.com/in/carol,Bob Owner,https://x.com/in/bob,2026-08-02,,"hello",INBOX\n',
                         persona="Nobody Matching")
    check("an owner who never wrote is still recognised",
          "Bob Owner" not in {c.counterparty for c in convos},
          str([c.counterparty for c in convos]))

    if FAILURES:
        print(f"FAIL - LinkedIn edges ({FAILURES} failure(s))")
        return 1
    print("PASS - LinkedIn edges: identity, group threads, corrupt counts, hostile CSV")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
