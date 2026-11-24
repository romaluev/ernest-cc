#!/usr/bin/env python3
"""LinkedIn inbound grading: the decision ORDER, the spam threshold, and the
"missing is not zero" rule — the three things that cost real money when wrong.

Guarantees:
  1. Suppression and hold run BEFORE any tier is assigned (order = safety).
  2. Tier-1 needs a WHO, not a title.
  3. Spam is scored, not matched — one template phrase never ignores anyone.
  4. Blank counts score nothing; a real 0 is evidence.
  5. Identity dedup collapses slug and member-URN shapes.
  6. The documented weights match the code (docs stay subordinate to code).
  7. A deleted rubric key is detectable, not silent.
  8. Emitted signals are real HubSpot enum values, never invented ones.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ernest import config  # noqa: E402
from ernest.grading import (  # noqa: E402
    _DEFAULTS, LINKEDIN_SPAM_WEIGHTS, LINKEDIN_WEIGHTS, SPAM_THRESHOLD,
    grade_linkedin_inbound, identity_key,
)

FAILURES = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global FAILURES
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES += 1


def main() -> int:
    cfg = config.load()

    def g(**kw):
        return grade_linkedin_inbound(cfg=cfg, **kw)

    # 1. ORDER. Every case below carries a STRONG tier-1 payload on purpose: if
    #    the branches are ever reordered, the payload wins and this fails loudly.
    bait = dict(headline="Founder & CEO at an AI studio and production studio",
                note="We want an enterprise plan, procurement started, 40 seats, volume pricing.",
                mutual_connections=50, location="United States")

    r = g(**bait, suppression_lists=["411"])
    check("suppression beats every tier-1 signal", r.tier == "hold", f"got {r.tier}")
    check("suppression emits Do Not Contact", r.signal == "Do Not Contact", r.signal)

    r = g(**{**bait, "headline": "Senior Reporter at Forbes and founder of an AI studio"})
    check("press beats tier-1 signals", r.tier == "hold", f"got {r.tier}")
    # The proposed action must be a hold, not an Ignore/Accept. Substring-matching
    # "ignore" would match the copy "do not ignore" — assert the verb instead.
    check("press proposes a hold, never an Ignore or Accept",
          r.action.startswith("Hold") and r.action.split()[0] not in ("Ignore", "Accept"), r.action)

    # Take a competitor from whatever rubric is loaded rather than hardcoding a
    # name. This suite ships inside the standalone bundle, where the rubric may
    # be the real one — the BEHAVIOUR is what must hold, not one demo list.
    rubric = json.loads((ROOT / "data" / "grading" / "linkedin-rubric.json").read_text(encoding="utf-8"))
    competitors = rubric.get("hold", {}).get("competitor_keywords") or []
    check("the rubric names at least one competitor", bool(competitors),
          "hold.competitor_keywords is empty — that check is switched off")
    if competitors:
        r = g(**{**bait, "headline": f"Head of Product at {competitors[0]}, ex-AI studio founder"})
        check("competitor beats tier-1 signals", r.tier == "hold", f"got {r.tier}")
        check("competitor is Do Not Contact, not Positive", r.signal == "Do Not Contact", r.signal)

    r = g(**bait, suppression_lists=["399"])
    check("employees are accepted, not trashed",
          r.tier == "tier-1" and r.action == "Accept", f"{r.tier}/{r.action}")

    r = g(headline="VP Marketing", company="Unknown Co", crm_tier="vip")
    check("CRM tier short-circuits inference",
          r.tier == "tier-1" and r.confidence == "high", f"{r.tier}/{r.confidence}")

    # 2. Tier-1 needs a WHO. A title and a good passport are not a buyer.
    r = g(headline="Vice President, Director of Growth", location="United States",
          mutual_connections=40)
    check("seniority + country + mutuals alone is NOT tier-1", r.tier == "tier-2", r.tier)
    r = g(headline="Head of Growth at an AI studio",
          note="exploring an enterprise plan for our team")
    check("archetype + seniority + intent IS tier-1", r.tier == "tier-1", r.tier)

    # 3. Spam is scored. One phrase is not proof.
    r = g(headline="Product Manager",
          note="Hope this message finds you well, I came across your profile.")
    check("one template phrase does not ignore anyone", r.tier == "tier-2", r.tier)
    check("but the evidence is surfaced as a flag",
          any("spam signal" in f for f in r.flags), str(r.flags))
    r = g(headline="Growth Hacker | I help CEOs scale | DM me",
          note="We offer SEO services and link building. Book a call with me.",
          mutual_connections=0, connections=11)
    check("stacked structural evidence IS spam", r.tier == "trash", r.tier)
    check("vendor pitches emit Seller Pitch", r.signal == "Seller Pitch", r.signal)
    check("spam score cleared the threshold", r.score >= SPAM_THRESHOLD, str(r.score))

    # 4. Missing is not zero — the difference between the archive rung quietly
    #    under-detecting spam and it falsely accusing everyone it cannot see.
    kw = dict(headline="Growth Hacker | DM me", note="We offer SEO services.")
    blank, zeroed = g(**kw), g(**kw, mutual_connections=0, connections=10)
    check("blank counts score nothing", blank.score < zeroed.score,
          f"blank={blank.score} zeroed={zeroed.score}")
    check("a real 0 is evidence",
          any("No mutual" in x for x in zeroed.reasons), str(zeroed.reasons))

    # 5. Identity dedup across LinkedIn's two identifier shapes.
    check("slug wins over urn",
          identity_key("https://www.linkedin.com/in/jane-doe/", "ACoAA123") == "slug:jane-doe")
    check("trailing query is stripped",
          identity_key("https://www.linkedin.com/in/jane-doe?trk=x") == "slug:jane-doe")
    check("urn is the fallback", identity_key("", "ACoAA123") == "urn:acoaa123")
    check("name is the last resort", identity_key(name="Jane  Doe") == "name:jane-doe")

    # 6. Docs stay subordinate to code.
    ref = (ROOT / "skills" / "linkedin-invitations" / "references" / "rubric.md").read_text(encoding="utf-8")
    check(f"reference documents the spam threshold {SPAM_THRESHOLD:g}",
          re.search(rf"threshold\D{{0,24}}{SPAM_THRESHOLD:g}\b", ref, re.I) is not None)
    for key, weight in (("buyer_archetypes", LINKEDIN_WEIGHTS["buyer_archetype"]),
                        ("intent_keywords", LINKEDIN_WEIGHTS["intent"]),
                        ("providers", LINKEDIN_WEIGHTS["provider"])):
        check(f"reference documents +{weight:g} for tier1.{key}",
              re.search(rf"`tier1\.{key}`\s*\|\s*\+{weight:g}", ref) is not None)
    for key, weight in (("vendor_keywords", LINKEDIN_SPAM_WEIGHTS["vendor_phrase"]),
                        ("template_fingerprints", LINKEDIN_SPAM_WEIGHTS["template_note"])):
        check(f"reference documents +{weight:g} for spam.{key}",
              re.search(rf"`spam\.{key}`[^|]*\|\s*\+{weight:g}", ref) is not None)

    # 7. The wholesale-replace footgun is detectable rather than silent.
    rubric = json.loads((ROOT / "data" / "grading" / "linkedin-rubric.json").read_text(encoding="utf-8"))
    missing = [k for k in _DEFAULTS["linkedin"] if k not in rubric]
    check("shipped rubric carries every signal family", not missing, f"missing {missing}")
    check("the code default and the skeleton agree on the threshold",
          _DEFAULTS["linkedin"]["spam"]["threshold"] == SPAM_THRESHOLD)
    check("the shipped rubric exposes the threshold as a tunable knob",
          rubric["spam"].get("threshold") == SPAM_THRESHOLD,
          str(rubric["spam"].get("threshold")))

    # 8. HubSpot's vocabulary is emitted verbatim, never invented.
    allowed = {"Positive", "Negative", "Seller Pitch", "JOB_SEEKER",
               "Do Not Contact", "Spam", "None"}
    seen = {g(**case).signal for case in (
        bait,
        {"headline": "Senior Reporter at Forbes"},
        {"headline": "ML Engineer #OpenToWork"},
        {"headline": "Growth Hacker | DM me", "note": "We offer SEO services",
         "mutual_connections": 0, "connections": 5},
        {"headline": "nobody in particular"})}
    check("every emitted signal is a real HubSpot enum value", seen <= allowed, str(seen - allowed))

    if FAILURES:
        print(f"FAIL - LinkedIn grading ({FAILURES} failure(s))")
        return 1
    print("PASS - LinkedIn grading: order, thresholds, missing-vs-zero, identity, docs parity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
