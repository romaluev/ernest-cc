#!/usr/bin/env python3
"""The LinkedIn action layer refuses correctly.

These are the properties that make report-first real. Every one of them is a
refusal, because the expensive failures here are all "it acted when it should
not have":

  1. dry_run is the DEFAULT, and `approved: false` keeps it dry even if flipped.
  2. never_auto actions refuse without an explicit named-list flag, every run.
  3. A batch naming nobody is refused — approval is per person, not per category.
  4. Caps are counted from the AUDIT LOG, so a crashed run still counted.
  5. `hold` rows can never reach a batch, by any route.
  6. Policy parses out of ernest.yaml; an unreadable file falls back to SAFE.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "adapters" / "linkedin"))

import act  # noqa: E402
import cli_common as cc  # noqa: E402

FAILURES = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global FAILURES
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES += 1


def _csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "tier,signal,score,confidence,action,name,public_url,identity_key,why\n"
        "trash,Seller Pitch,22,high,Ignore,Spammer One,https://x/in/a,slug:a,vendor\n"
        "trash,Seller Pitch,18,high,Ignore,Spammer Two,https://x/in/b,slug:b,vendor\n"
        "hold,Do Not Contact,0,medium,Hold — do not accept unread,A Competitor,https://x/in/c,slug:c,competitor\n"
        "tier-1,Positive,55,high,Accept,Real Buyer,https://x/in/d,slug:d,archetype\n",
        encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        profile = Path(tmp) / "p"
        profile.mkdir(parents=True)
        csv_path = profile / "graded.csv"
        _csv(csv_path)

        # 6. Policy comes from the repo's ernest.yaml when the profile has none.
        policy = act.load_policy(profile)
        check("policy parses caps from ernest.yaml",
              policy["caps_per_day"]["ignore"] == 100, str(policy["caps_per_day"]))
        check("policy parses never_auto", "report_spam" in policy["never_auto"],
              str(policy["never_auto"]))
        check("dry_run defaults TRUE", policy["dry_run"] is True)
        check("approved defaults FALSE", policy["approved"] is False)

        # 5. hold never reaches a batch — not by tier default, not by --action.
        for tier, action in (("trash", None), ("tier-2", "ignore")):
            batch = act.plan(profile, csv_path, tier=tier, action=action,
                             limit=None, policy=policy)
            tiers = {i["tier"] for i in batch["items"]}
            check(f"plan(tier={tier}) never includes a hold row", "hold" not in tiers, str(tiers))

        batch = act.plan(profile, csv_path, tier="trash", action=None, limit=None, policy=policy)
        check("plan selects the spam rows", batch["count"] == 2, str(batch["count"]))
        check("plan names every person by identity key",
              all(i["identity_key"] for i in batch["items"]))
        check("plan ranks by score",
              [i["identity_key"] for i in batch["items"]] == ["slug:a", "slug:b"])
        check("proposals hit the decision journal",
              (profile / policy["decision_journal"]).is_file())

        # 1. Dry run is the default and it writes DRYRUN, never DONE.
        res = act.execute(profile, batch, policy=policy, prefer="auto", dry_run=True)
        check("dry run executes nothing", res["executed"] == 0 and res["dry_run"])
        audit = (profile / policy["audit_log"]).read_text(encoding="utf-8")
        check("dry run audits as DRYRUN, not DONE", "DRYRUN" in audit and "|DONE|" not in audit)

        # 4. Caps count from the audit log, so a crash mid-run is not free.
        check("a DRYRUN does not consume the cap",
              act.remaining(profile, policy, "ignore") == 100,
              str(act.remaining(profile, policy, "ignore")))
        for i in range(100):
            act._audit(profile, policy, "ignore", "DONE", f"slug:x{i}")
        check("DONE lines consume the cap", act.remaining(profile, policy, "ignore") == 0)
        check("other actions are unaffected", act.remaining(profile, policy, "accept") == 25)

        # 2 + 3. CLI-level refusals, asserted on the exit code a scheduler sees.
        batch_path = act.write_batch(profile, batch)
        check("the written batch is marked DRAFT",
              json.loads(batch_path.read_text())["STATUS"] == "DRAFT")

        argv = ["--profile-dir", str(profile), "--execute", str(batch_path)]
        check("spent cap refuses with exit 6", act.main(argv) == cc.REFUSED)

        spam = profile / "spam.json"
        spam.write_text(json.dumps({**json.loads(batch_path.read_text()),
                                    "action": "report_spam"}), encoding="utf-8")
        rc = act.main(["--profile-dir", str(profile), "--execute", str(spam)])
        check("never_auto refuses without the named-list flag (exit 6)", rc == cc.REFUSED, str(rc))

        empty = profile / "empty.json"
        empty.write_text(json.dumps({**json.loads(batch_path.read_text()), "items": []}),
                         encoding="utf-8")
        rc = act.main(["--profile-dir", str(profile), "--execute", str(empty)])
        check("a batch naming nobody refuses (exit 2)", rc == cc.USAGE, str(rc))

        rc = act.main(["--profile-dir", str(profile), "--execute", str(profile / "nope.json")])
        check("a missing batch is not-found (exit 3)", rc == cc.NOT_FOUND, str(rc))

    if FAILURES:
        print(f"FAIL - LinkedIn actions ({FAILURES} failure(s))")
        return 1
    print("PASS - LinkedIn actions: dry-run default, never_auto, named lists, caps, hold safety")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
