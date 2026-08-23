#!/usr/bin/env python3
"""Value weighting, commitments, deadlines, thread state, campaigns, diffs.

These are the judgments that decide whether the report is worth reading. The
assertions below are all about NOT surfacing things: an unidentified stranger
cannot inflate anything, a vague intro is not a task, a delivered promise is not
outstanding, and forty copies of one blast are one judgment.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ernest import config  # noqa: E402
from ernest.li_insight import (  # noqa: E402
    CAMPAIGN_SIMILARITY, campaigns, commitments, deadlines, diff_runs,
    reply_brief, thread_state, unify, value_of,
)

FAILURES = 0
TODAY = date(2026, 8, 24)


def check(label: str, cond: bool, detail: str = "") -> None:
    global FAILURES
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES += 1


@dataclass
class M:
    at: Optional[date]
    direction: str
    body: str


def main() -> int:
    cfg = config.load()

    # --- value: facts outrank inference, unknown is capped -------------------
    customer = value_of(cfg=cfg, company="Apex Bank", crm_tier="vip", open_deal=True,
                        won_revenue=180000, prior_contact=True, ever_replied=True,
                        outbound_count=3, message_count=8)
    loud_stranger = value_of(cfg=cfg, text="enterprise rollout, procurement started, "
                                           "40 seats, company-wide, annual plan", message_count=1)
    check("a real commercial relationship is critical", customer.band == "critical", customer.band)
    check("its evidence is recorded as FACTS", len(customer.facts) >= 3, str(customer.facts))
    check("an unidentified stranger is capped at low",
          loud_stranger.band == "low", f"{loud_stranger.band} @ {loud_stranger.score}")
    check("...even though their raw score would rank higher",
          loud_stranger.score > 20, str(loud_stranger.score))
    check("...and they are flagged worth identifying, not buried",
          loud_stranger.needs_identification)
    check("facts always outrank inference", customer.score > loud_stranger.score)
    check("an empty stranger is noise",
          value_of(cfg=cfg, name="Someone", message_count=1).band == "noise")
    check("revenue is log-scaled, not linear",
          (value_of(cfg=cfg, won_revenue=4_000_000).score
           - value_of(cfg=cfg, won_revenue=2_000_000).score) <
          (value_of(cfg=cfg, won_revenue=50_000).score
           - value_of(cfg=cfg, won_revenue=0).score))

    # --- commitments --------------------------------------------------------
    def one(body, val=customer, extra=()):
        msgs = [M(date(2026, 6, 1), "outbound", body), *extra]
        got = commitments(msgs, today=TODAY, value=val)
        return got[0] if got else None

    check("a promise is found", one("I'll send the pricing sheet this week.") is not None)
    check("an ASK is not a promise", one("Let me know if you'd like the deck.") is None)
    check("a delivered promise is dropped",
          one("I'll send the deck.", extra=[M(date(2026, 6, 2), "outbound",
                                              "Attached — here's the deck.")]).drop_reason
          == "already delivered")
    vague = one("I'll intro you to someone who can help.")
    check("a vague intro is dropped", vague.drop_reason == "intro with no named subject",
          vague.drop_reason)
    named = one("I'll introduce you to Dana at Kestrel Media.")
    check("a NAMED intro survives", named.actionable, named.drop_reason)
    check("an intro to an unidentified counterparty is dropped",
          one("I'll introduce you to Dana at Kestrel.",
              val=value_of(cfg=cfg, name="X", message_count=1)).drop_reason != "")
    chased = commitments(
        [M(date(2026, 6, 1), "outbound", "I'll send pricing."),
         M(date(2026, 8, 1), "inbound", "Any update on that pricing?")],
        today=TODAY, value=customer)[0]
    quiet = one("I'll send pricing.")
    check("being chased raises the value", chased.value > quiet.value,
          f"{chased.value} vs {quiet.value}")
    check("legal/payment outranks a courtesy",
          one("I'll get the MSA over for signature.").value > named.value)
    check("an ancient unchased courtesy goes stale",
          commitments([M(date(2024, 1, 5), "outbound", "I'll share a case study.")],
                      today=TODAY,
                      value=value_of(cfg=cfg, company="X", won_revenue=28000,
                                     prior_contact=True))[0].drop_reason.startswith("stale"))

    # --- deadlines: resolved against the MESSAGE date ------------------------
    ds = deadlines([M(date(2026, 6, 10), "inbound", "We need the quote by Friday.")])
    check("a deadline resolves against when it was written",
          ds and ds[0].due == date(2026, 6, 12), str(ds[0].due if ds else None))
    check("...and reads as long passed", ds[0].status(TODAY).startswith("passed"))
    check("a phrase stops at the clause break",
          deadlines([M(date(2026, 6, 10), "inbound",
                       "by Friday, our board meets before the 15th.")])[0].phrase == "by Friday")
    check("our own 'by Friday' is not their deadline",
          deadlines([M(date(2026, 6, 10), "outbound", "I'll have it by Friday.")]) == [])

    # --- thread state -------------------------------------------------------
    cold = thread_state([M(date(2026, 8, 1), "inbound", "Quick question - we offer SEO.")],
                        today=TODAY)
    check("a cold pitch containing 'question' is still cold", cold.stage == "cold", cold.stage)
    deal = [M(date(2026, 6, 1), "inbound", "Interested in a pilot."),
            M(date(2026, 6, 2), "outbound", "Happy to set up a call."),
            M(date(2026, 6, 9), "inbound", "What's pricing for 30 seats annual?")]
    st = thread_state(deal, today=TODAY, open_commitments=[])
    check("a live negotiation is recognised", st.stage == "negotiating", st.stage)
    closed = thread_state([M(date(2026, 5, 1), "inbound", "We decided to go with another vendor.")],
                          today=TODAY)
    check("a closed thread owes nobody", closed.owes == "nobody", closed.owes)

    # --- campaigns ----------------------------------------------------------
    blast = "Quick question - I came across your profile and we help {} scale with dedicated developers. Worth a chat?"
    items = [("a", blast.format("founders")), ("b", blast.format("CEOs")),
             ("c", "Hi! Quick question, came across your profile - we help founders scale using dedicated developers. Worth a chat?"),
             ("real1", "We're an AI audio studio moving into video, wondering about enterprise pricing."),
             ("real2", "Congrats on the launch, looked great!")]
    cs = campaigns(items)
    check("spintax variants cluster into one campaign", len(cs) == 1 and cs[0].size == 3,
          str([(c.size, c.members) for c in cs]))
    swept = {m for c in cs for m in c.members}
    check("genuine messages are never swept in", not (swept & {"real1", "real2"}), str(swept))
    check("two similar messages are not a campaign",
          campaigns(items[:2]) == [], "min members is 3")
    check("the threshold is documented where it is used", 0.3 <= CAMPAIGN_SIMILARITY <= 0.6)

    # --- one person, both surfaces -----------------------------------------
    @dataclass
    class Inv:
        name: str
        public_url: str
        key: str

    @dataclass
    class Conv:
        counterparty: str
        counterparty_url: str

    people = unify([Inv("Dana Reed", "https://www.linkedin.com/in/dana-reed", "slug:dana-reed")],
                   [Conv("Dana Reed", "https://www.linkedin.com/in/dana-reed")])
    check("the same human collapses to one row", len(people) == 1, str(len(people)))
    check("...and is marked as both surfaces", people[0].multi and "invitation" in people[0].surfaces)

    # --- run diffs ----------------------------------------------------------
    d = diff_runs({"items": {"a": {"bucket": "needs-reply", "days_waiting": 10},
                             "gone": {"bucket": "fyi"}}},
                  {"items": {"a": {"bucket": "escalation", "days_waiting": 24},
                             "fresh": {"bucket": "needs-reply", "days_waiting": 1}}})
    check("new threads are reported", d.new == ["fresh"], str(d.new))
    check("cleared threads are reported", d.resolved == ["gone"], str(d.resolved))
    check("a thread that got more urgent is flagged", d.escalated == ["a"], str(d.escalated))
    check("aging is tracked", d.still_waiting[0] == ("a", 24), str(d.still_waiting))

    # --- reply brief --------------------------------------------------------
    brief = reply_brief(counterparty="Nobody", messages=[M(date(2026, 8, 20), "inbound", "Can we chat?")],
                        value=value_of(cfg=cfg, name="Nobody", message_count=1),
                        state=thread_state([M(date(2026, 8, 20), "inbound", "Can we chat?")], today=TODAY),
                        today=TODAY)
    check("a brief for an unknown forbids inventing a relationship",
          any("cannot identify" in x for x in brief.do_not), str(brief.do_not))
    check("...and forbids referencing revenue we do not have",
          any("no CRM record" in x for x in brief.do_not))
    rich = reply_brief(counterparty="Apex", messages=[M(date(2026, 8, 1), "inbound", "Any update on pricing?")],
                       value=customer,
                       state=thread_state(deal, today=TODAY),
                       open_commitments=commitments([M(date(2026, 6, 1), "outbound", "I'll send pricing.")],
                                                    today=TODAY, value=customer),
                       today=TODAY)
    check("a brief with an unkept promise demands delivery or a date",
          any("Deliver, or give a date" in x for x in rich.must_include), str(rich.must_include))

    if FAILURES:
        print(f"FAIL - LinkedIn insight ({FAILURES} failure(s))")
        return 1
    print("PASS - LinkedIn insight: value caps, commitment filtering, deadlines, "
          "state, campaigns, diffs, briefs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
