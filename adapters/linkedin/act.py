#!/usr/bin/env python3
"""Act on approved LinkedIn invitation batches. Report-first, always.

Two phases, and they are separate commands on purpose:

    plan     read the graded CSV, propose a batch, write it to 00-Drafts/
    execute  perform ONLY the identity keys named in an approved batch file

Nothing here runs on a schedule and nothing acts on a category. `--tier trash`
selects rows to *propose*; execution still requires the batch file listing every
person by identity key. "Ignore all the spam" must survive being wrong about one
person, so the approval names them.

Policy lives in `ernest.yaml: linkedin_policy`, not in this file:
  dry_run / approved     master switches; dry_run defaults TRUE
  caps_per_day           accept · ignore · report_spam
  never_auto             actions that require an explicit named list every time
  min_action_interval_seconds

Reversibility sets the ceiling. Accept and Ignore can be undone; reporting
someone as spam cannot, and it affects their account, so it never graduates past
explicit per-run approval no matter how clean the history looks.

Exit codes: see cli_common.EXIT_MEANING (6 = refused by policy).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import browser  # noqa: E402
import cli_common as cc  # noqa: E402

INVITATION_MANAGER = "https://www.linkedin.com/mynetwork/invitation-manager/received/"
MESSAGING = "https://www.linkedin.com/messaging/"
# Invitation actions and DM actions share one batch/execute path. Reversibility
# is what separates them, not which surface they run on.
ACTIONS = ("accept", "ignore", "report_spam", "archive", "delete")

_DEFAULT_POLICY: Dict[str, Any] = {
    "dry_run": True,
    "approved": False,
    "caps_per_day": {"accept": 25, "ignore": 100, "report_spam": 25,
                     "archive": 200, "delete": 25},
    "never_auto": ["report_spam", "delete", "reply", "inmail"],
    "min_action_interval_seconds": 20,
    "audit_log": "logs/linkedin-actions.log",
    "decision_journal": "logs/linkedin-decisions.jsonl",
}


# --------------------------------------------------------------------------- #
# Policy
# --------------------------------------------------------------------------- #

def load_policy(profile: Path) -> Dict[str, Any]:
    """Read linkedin_policy out of ernest.yaml without a YAML dependency.

    The engine hand-parses its own YAML (no PyYAML anywhere), so this does the
    same for the one block it needs. A file we cannot read means we fall back to
    the SAFEST defaults, never to permissive ones.
    """
    policy = json.loads(json.dumps(_DEFAULT_POLICY))
    path = profile / "ernest.yaml"
    if not path.is_file():
        path = Path(__file__).resolve().parents[2] / "ernest.yaml"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return policy
    block = re.search(r"^linkedin_policy:\n((?:[ \t]+.*\n|\n)*)", text, re.M)
    if not block:
        return policy
    body = block.group(1)
    for key in ("dry_run", "approved"):
        m = re.search(rf"^\s+{key}:\s*(\S+)", body, re.M)
        if m:
            policy[key] = m.group(1).strip().lower() in ("true", "yes", "on", "1")
    caps = re.search(r"^\s+caps_per_day:\n((?:\s{4,}\w+:\s*\d+\n)+)", body, re.M)
    if caps:
        for name, value in re.findall(r"(\w+):\s*(\d+)", caps.group(1)):
            policy["caps_per_day"][name] = int(value)
    m = re.search(r"^\s+min_action_interval_seconds:\s*(\d+)", body, re.M)
    if m:
        policy["min_action_interval_seconds"] = int(m.group(1))
    never = re.search(r"^\s+never_auto:\n((?:\s+-\s*\w+.*\n)+)", body, re.M)
    if never:
        policy["never_auto"] = [x for x in re.findall(r"-\s*(\w+)", never.group(1))]
    for key in ("audit_log", "decision_journal"):
        m = re.search(rf'^\s+{key}:\s*"?([^"\n]+)"?', body, re.M)
        if m:
            policy[key] = m.group(1).strip()
    return policy


def _audit_path(profile: Path, policy: Dict[str, Any]) -> Path:
    return profile / policy.get("audit_log", _DEFAULT_POLICY["audit_log"])


def used_today(profile: Path, policy: Dict[str, Any], action: str,
               today: Optional[date] = None) -> int:
    """Count from the AUDIT LOG, not from memory — a crashed run still counted."""
    day = (today or datetime.now(timezone.utc).date()).isoformat()
    path = _audit_path(profile, policy)
    if not path.is_file():
        return 0
    n = 0
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            parts = line.split("|")
            if len(parts) >= 3 and parts[0].startswith(day) and parts[1] == action \
                    and parts[2] == "DONE":
                n += 1
    except OSError:
        return 0
    return n


def remaining(profile: Path, policy: Dict[str, Any], action: str) -> int:
    cap = int(policy.get("caps_per_day", {}).get(action, 0))
    return max(0, cap - used_today(profile, policy, action))


def _audit(profile: Path, policy: Dict[str, Any], action: str, state: str,
           key: str, detail: str = "") -> None:
    path = _audit_path(profile, policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}|{action}|{state}|{key}|{detail}\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, line.encode())
    finally:
        os.close(fd)


def _journal(profile: Path, policy: Dict[str, Any], record: Dict[str, Any]) -> None:
    """Every proposal + what the human actually did.

    This is the learning signal. Override rate per tier and per signal is an
    outcome measure with N = every interaction, which is the only kind of
    evaluation available at this volume.
    """
    path = profile / policy.get("decision_journal", _DEFAULT_POLICY["decision_journal"])
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"at": cc.now_iso(), **record}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


# --------------------------------------------------------------------------- #
# Plan
# --------------------------------------------------------------------------- #

_TIER_TO_ACTION = {"trash": "ignore", "tier-1": "accept"}
# DM buckets. Archiving is reversible (LinkedIn keeps the thread); deleting is
# not, so it sits under never_auto alongside reporting.
_BUCKET_TO_ACTION = {"trash": "archive", "fyi": "archive"}


def plan(profile: Path, csv_path: Path, *, tier: str, action: Optional[str],
         limit: Optional[int], policy: Dict[str, Any], dms: bool = False) -> Dict[str, Any]:
    if not csv_path.is_file():
        raise FileNotFoundError(f"No graded CSV at {csv_path}. Run `ernest grade --linkedin` first.")
    act = action or (_BUCKET_TO_ACTION if dms else _TIER_TO_ACTION).get(tier)
    if act not in ACTIONS:
        raise ValueError(f"No default action for tier {tier!r}; pass --action {'|'.join(ACTIONS)}")
    cap_left = remaining(profile, policy, act)
    want = min(limit or cap_left, cap_left)

    key = "bucket" if dms else "tier"
    rows: List[Dict[str, str]] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get(key) != tier:
                continue
            # Belt and braces. `hold` and `escalation` must never reach a batch
            # even if a caller asks for them by name, and a thread still owed a
            # reply is never archived in bulk — those are the two ways this could
            # quietly bury something that mattered.
            if row.get(key) in ("hold", "escalation"):
                continue
            if row.get("action", "").startswith("Hold") or row.get("action", "").startswith("Answer"):
                continue
            if dms and row.get("owed") == "yes" and row.get(key) != "trash":
                continue
            rows.append(row)
    rows.sort(key=lambda r: -float(r.get("score") or 0))
    selected, skipped = rows[:want], rows[want:]

    batch = {
        "created": cc.now_iso(),
        "action": act,
        "tier": tier,
        "source_csv": str(csv_path),
        "cap_remaining_at_plan": cap_left,
        "requires_named_approval": act in policy.get("never_auto", []),
        "count": len(selected),
        "not_included": len(skipped),
        "surface": "dms" if dms else "invitations",
        "items": [{"identity_key": r.get("identity_key") or r.get("conversation_id", ""),
                   "name": r.get("name") or r.get("counterparty", ""),
                   "public_url": r.get("public_url", ""),
                   "tier": r.get(key, ""), "signal": r.get("signal", ""),
                   "score": r.get("score", ""), "why": r.get("why", "")} for r in selected],
    }
    for item in batch["items"]:
        _journal(profile, policy, {"phase": "proposed", "action": act,
                                   "surface": batch["surface"],
                                   "identity_key": item["identity_key"],
                                   "tier": item["tier"], "signal": item["signal"]})
    return batch


def write_batch(profile: Path, batch: Dict[str, Any]) -> Path:
    vault = Path(os.environ.get("ERNEST_LOCAL_VAULT", profile / "vault"))
    drafts = vault / "Ernest" / "00-Drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = drafts / f"linkedin-{batch['action']}--{stamp}.json"
    path.write_text(json.dumps({"STATUS": "DRAFT", **batch}, indent=2) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Execute
# --------------------------------------------------------------------------- #

_FIND_JS = r"""
(() => {
  const rows = [];
  for (const b of document.querySelectorAll('button, a')) {
    const aria = b.getAttribute('aria-label') || '';
    let m = aria.match(/^Accept (.+?)[’']s invitation$/);
    if (m) { rows.push({name: m[1], verb: 'accept', tag: b.tagName}); continue; }
    m = aria.match(/^Ignore an invitation to connect from (.+)$/i);
    if (m) rows.push({name: m[1], verb: 'ignore', tag: b.tagName});
  }
  return rows;
})()
"""


_FIND_DM_JS = r"""
(() => {
  // Conversation rows carry the counterparty name in the list item; the
  // overflow menu is what exposes Archive/Delete. Names are the only stable
  // handle — LinkedIn's class names are hashed and change without notice.
  const rows = [];
  for (const li of document.querySelectorAll('li.msg-conversation-listitem, li[class*="conversation"]')) {
    const nameEl = li.querySelector('h3, [class*="participant-names"], [class*="conversation-card__title"]');
    const name = (nameEl ? nameEl.innerText : '').replace(/\s+/g, ' ').trim();
    if (name) rows.push({name: name, verb: 'archive', tag: 'LI'});
  }
  return rows;
})()
"""


def _click_dm_js(verb: str, name: str) -> str:
    """Open a thread's overflow menu and click Archive (or Delete)."""
    label = "Archive" if verb == "archive" else "Delete"
    return r"""
(() => {
  const want = %s, label = %s;
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const li = Array.from(document.querySelectorAll('li.msg-conversation-listitem, li[class*="conversation"]'))
    .find(el => norm(el.innerText).includes(want));
  if (!li) return {ok:false, why:'thread not on this page'};
  const menu = li.querySelector('button[aria-label*="ptions" i], button[class*="overflow"]');
  if (!menu) return {ok:false, why:'no overflow menu on the row'};
  menu.click();
  const item = Array.from(document.querySelectorAll('div[role=menu] button, ul[role=menu] button, button'))
    .find(b => norm(b.innerText).toLowerCase() === label.toLowerCase());
  if (!item) return {ok:false, why:'menu opened but no ' + label + ' item'};
  item.click();
  return {ok:true};
})()
""" % (json.dumps(name), json.dumps(label))


def _click_js(verb: str, name: str) -> str:
    if verb in ("archive", "delete"):
        return _click_dm_js(verb, name)
    pattern = ("^Accept " if verb == "accept" else "^Ignore an invitation to connect from ")
    return """
(() => {
  const want = %s;
  const els = Array.from(document.querySelectorAll('button, a')).filter(b => {
    const a = b.getAttribute('aria-label') || '';
    return a.startsWith(%s) && a.includes(want);
  });
  if (!els.length) return {ok:false, why:'no control for that person on this page'};
  const el = els[0];
  // A premium "Follows you" card renders Accept as an <a> whose handler no
  // click method reaches. Refuse rather than report a success that never was.
  if (el.tagName === 'A') return {ok:false, why:'accept-is-anchor', tag:'A'};
  el.click();
  return {ok:true};
})()
""" % (json.dumps(name), json.dumps(pattern.replace("^", "")))


def execute(profile: Path, batch: Dict[str, Any], *, policy: Dict[str, Any],
            prefer: str, dry_run: bool) -> Dict[str, Any]:
    action = batch["action"]
    done: List[str] = []
    refused: List[Dict[str, str]] = []
    cap_left = remaining(profile, policy, action)
    pace = int(policy.get("min_action_interval_seconds", 20))

    if dry_run:
        for item in batch["items"][:cap_left]:
            _audit(profile, policy, action, "DRYRUN", item["identity_key"], item["name"])
        return {"executed": 0, "would_execute": min(len(batch["items"]), cap_left),
                "cap_remaining": cap_left, "dry_run": True, "refused": refused}

    surface_url = MESSAGING if action in ("archive", "delete") else INVITATION_MANAGER
    drv = browser.open_driver(prefer)
    try:
        by_name = {i["name"]: i for i in batch["items"] if i.get("name")}
        stalled = 0
        while by_name and len(done) < cap_left and stalled < 3:
            drv.goto(surface_url)
            time.sleep(3)
            present = drv.evaluate(_FIND_DM_JS if action in ("archive", "delete") else _FIND_JS) or []
            hit = False
            for row in present:
                name = row.get("name", "")
                if name not in by_name or len(done) >= cap_left:
                    continue
                item = by_name[name]
                res = drv.evaluate(_click_js(action, name)) or {}
                if res.get("ok"):
                    done.append(item["identity_key"])
                    _audit(profile, policy, action, "DONE", item["identity_key"], name)
                    _journal(profile, policy, {"phase": "executed", "action": action,
                                               "identity_key": item["identity_key"],
                                               "tier": item.get("tier"),
                                               "signal": item.get("signal")})
                else:
                    refused.append({"name": name, "why": res.get("why", "unknown")})
                    _audit(profile, policy, action, "REFUSED", item["identity_key"],
                           res.get("why", "unknown"))
                by_name.pop(name, None)
                hit = True
                time.sleep(pace)   # pacing IS the safety property; do not remove
            stalled = 0 if hit else stalled + 1
        for name, item in by_name.items():
            refused.append({"name": name, "why": "not found in the queue (withdrawn or already handled)"})
            _audit(profile, policy, action, "MISSING", item["identity_key"], name)
        return {"executed": len(done), "cap_remaining": cap_left - len(done),
                "dry_run": False, "refused": refused, "keys": done}
    finally:
        drv.close()


# --------------------------------------------------------------------------- #

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Act on approved LinkedIn invitation batches (report-first)",
        epilog="Exit codes: " + " · ".join(f"{k}={v}" for k, v in cc.EXIT_MEANING.items()))
    ap.add_argument("--profile-dir", default=os.environ.get("ERNEST_PROFILE_DIR", os.getcwd()))
    ap.add_argument("--plan", action="store_true", help="propose a batch from the graded CSV")
    ap.add_argument("--execute", metavar="BATCH_JSON", help="perform an approved batch")
    ap.add_argument("--from-csv", help="graded CSV (default: today's card sidecar)")
    ap.add_argument("--dms", action="store_true",
                    help="operate on the DM report instead of the invitation report")
    ap.add_argument("--tier", default="trash",
                    choices=["trash", "tier-1", "tier-2", "fyi", "needs-reply"],
                    help="invitation tier, or DM bucket with --dms")
    ap.add_argument("--action", choices=list(ACTIONS))
    ap.add_argument("--limit", type=int)
    ap.add_argument("--prefer", choices=["auto", "ego", "chrome"], default="auto")
    ap.add_argument("--i-approve-this-named-list", action="store_true",
                    help="required for actions listed under never_auto")
    ap.add_argument("--caps", action="store_true", help="show today's remaining caps")
    ap.add_argument("--rescue", metavar="IDENTITY_KEY", nargs="+",
                    help="this person should NOT have been proposed — record the override")
    ap.add_argument("--actual", default="", help="what they actually are (with --rescue)")
    ap.add_argument("--why", default="", help="one line of context (with --rescue)")
    cc.add_common_flags(ap)
    args = ap.parse_args(argv)
    cc.resolve_common(args)
    profile = Path(args.profile_dir).resolve()
    policy = load_policy(profile)

    if args.caps:
        results = {a: {"cap": policy["caps_per_day"].get(a, 0),
                       "used_today": used_today(profile, policy, a),
                       "remaining": remaining(profile, policy, a)} for a in ACTIONS}
        results["never_auto"] = policy["never_auto"]
        results["dry_run"] = policy["dry_run"]
        return cc.emit(cc.envelope(results, source="local", reason="caps"),
                       as_json=args.json, compact=args.compact, sink=args.deliver,
                       human="\n".join(
                           f"{a}: {results[a]['remaining']}/{results[a]['cap']} left today"
                           for a in ACTIONS) + f"\ndry_run: {policy['dry_run']}")

    if args.rescue:
        # The learning signal. There is no eval set at this volume, but every
        # proposal is kept or overridden, so override rate has N = every decision.
        # Three of the same shape become a reviewable rubric diff via `ernest learn`.
        for key in args.rescue:
            _journal(profile, policy, {"phase": "overridden", "action": "ignore",
                                       "identity_key": key, "actual": args.actual,
                                       "why": args.why})
            _audit(profile, policy, "rescue", "DONE", key, args.actual or args.why)
        if args.actual or args.why:
            cc.record_feedback(profile, f"LinkedIn: {' '.join(args.rescue)} was actually "
                                        f"{args.actual or 'not spam'}. {args.why}".strip())
        return cc.emit(cc.envelope({"rescued": args.rescue, "actual": args.actual},
                                   source="local", reason="override"),
                       as_json=args.json, compact=args.compact, sink=args.deliver,
                       human=f"Recorded {len(args.rescue)} override(s). "
                             "Three of the same shape become a rubric proposal.")

    if args.plan:
        vault = Path(os.environ.get("ERNEST_LOCAL_VAULT", profile / "vault"))
        stem = "linkedin-dms" if args.dms else "linkedin-invitations"
        default_csv = (vault / "Ernest" / "00-Watch" /
                       f"{stem}--{datetime.now(timezone.utc).date().isoformat()}.csv")
        try:
            batch = plan(profile, Path(args.from_csv) if args.from_csv else default_csv,
                         tier=args.tier, action=args.action, limit=args.limit,
                         policy=policy, dms=args.dms)
        except FileNotFoundError as exc:
            print(f"plan: {exc}", file=sys.stderr)
            return cc.NOT_FOUND
        except ValueError as exc:
            print(f"plan: {exc}", file=sys.stderr)
            return cc.USAGE
        path = write_batch(profile, batch)
        human = (f"Planned {batch['count']} × {batch['action']} "
                 f"({'bucket' if args.dms else 'tier'} {batch['tier']}). "
                 f"{batch['not_included']} more did not fit today's cap.\n"
                 f"Batch: {path}\n"
                 f"Review it, then: act.py --execute {path}"
                 + (" --i-approve-this-named-list" if batch["requires_named_approval"] else ""))
        return cc.emit(cc.envelope({**batch, "batch_path": str(path)}, source="local",
                                   reason="plan"),
                       as_json=args.json, compact=args.compact, sink=args.deliver, human=human)

    if args.execute:
        try:
            batch = json.loads(Path(args.execute).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"execute: cannot read batch ({exc})", file=sys.stderr)
            return cc.NOT_FOUND
        action = batch.get("action")
        if action not in ACTIONS:
            print(f"execute: batch names no valid action ({action!r})", file=sys.stderr)
            return cc.USAGE
        if not batch.get("items"):
            print("execute: batch names nobody. Approval is per person, not per category.",
                  file=sys.stderr)
            return cc.USAGE
        if action in policy.get("never_auto", []) and not args.i_approve_this_named_list:
            print(f"execute: {action!r} is listed under never_auto in ernest.yaml. It is not "
                  "reversible, so it needs --i-approve-this-named-list every single run.",
                  file=sys.stderr)
            return cc.REFUSED
        dry = args.dry_run or policy.get("dry_run", True) or not policy.get("approved", False)
        if remaining(profile, policy, action) <= 0:
            print(f"execute: daily cap for {action} is already spent "
                  f"({used_today(profile, policy, action)} used). Try tomorrow.", file=sys.stderr)
            return cc.REFUSED
        try:
            res = execute(profile, batch, policy=policy, prefer=args.prefer, dry_run=dry)
        except browser.BrowserUnavailable as exc:
            print(f"execute: {exc}", file=sys.stderr)
            return cc.UNREACHABLE
        human = (f"{'Would perform' if res['dry_run'] else 'Performed'} "
                 f"{res.get('would_execute', res['executed'])} × {action}. "
                 f"cap left: {res['cap_remaining']}."
                 + (f" refused: {len(res['refused'])}" if res["refused"] else "")
                 + ("\n(dry run — set linkedin_policy.dry_run=false and approved=true "
                    "in ernest.yaml to act for real)" if res["dry_run"] else ""))
        return cc.emit(cc.envelope(res, source="linkedin-live", reason=action),
                       as_json=args.json, compact=args.compact, sink=args.deliver, human=human)

    ap.print_help()
    return cc.USAGE


if __name__ == "__main__":
    raise SystemExit(main())
