#!/usr/bin/env python3
"""Ernest command-line engine.

    ernest start                       the one command: watch + brief
    ernest doctor                      health + config snapshot
    ernest onboard [--non-interactive] seed memory from answers
    ernest watch                       write remind-only cards
    ernest brief                       write + print the morning brief
    ernest draft --concern <id>        draft-only outreach for review
    ernest new-automation --id ...     register a concern + scaffold a skill
    ernest learn [--note "..."]        summarize self-improvement proposals
    ernest audit [--window 365d]       deep owed-reply sweep (chunked manifest)
    ernest read [--owed] [--thread ID] cache full thread bodies to vault
    ernest grade [--b2b] [--talent]    tier inbound leads + talent (ICP rubrics)

Local-first: every command works with no VPS and no live connectors, reading
exported data under `data/`. Nothing here ever sends.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, config
from . import (automations, audit, brief, concerns, draft, grade_run, learn,
               onboard, read_threads, watch)


def _connectors(cfg: config.Config) -> list[str]:
    if not cfg.mcp_file.is_file():
        return []
    try:
        data = json.loads(cfg.mcp_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return sorted(data.get("mcpServers", {}).keys())


def _diagnostics(cfg: config.Config) -> list[tuple[str, str]]:
    """Soft checks: (problem, how-to-fix). Never fail the health gate on these —
    they feed the self-repair skill so Ernest (or any user) can fix things."""
    issues: list[tuple[str, str]] = []

    for name in ("icp-b2b.md", "icp-talent.md"):
        if not (cfg.memory_dir / name).is_file():
            issues.append((f"ICP rubric memory missing: {name}",
                           "Restore from repo or run `./install.sh --refresh`."))
    for rel in ("grading/b2b-rubric.json", "grading/talent-rubric.json"):
        if not (cfg.data_dir / rel).is_file():
            issues.append((f"Grading rubric missing: data/{rel}",
                           "Restore the file or `./install.sh --refresh`; engine "
                           "falls back to built-in defaults meanwhile."))
    mail = cfg.data_dir / "mail"
    if not mail.is_dir() or not any(mail.iterdir()):
        issues.append(("No mail to read (data/mail is empty).",
                       "Drop exports in data/mail/ or connect a mail MCP "
                       "(docs/connectors.md). Then `ernest read --owed`."))
    if not _connectors(cfg):
        issues.append(("No MCP connectors configured (running on local exports).",
                       "To go live, add a connector. Ask Ernest: /ernest-doctor "
                       "(it can research and propose the right MCP server)."))
    for mod in ("ernest.watch", "ernest.grading", "ernest.read_threads", "ernest.audit"):
        try:
            __import__(mod)
        except Exception as exc:  # noqa: BLE001 - report any import breakage
            issues.append((f"Engine module failed to import: {mod} ({exc})",
                           "Run `/ernest-doctor` to diagnose and repair, or "
                           "`./install.sh --refresh`."))
    return issues


def cmd_doctor(cfg: config.Config, _args: argparse.Namespace) -> int:
    missing = [name for name in ("company-core.md", "ceo-persona.md", "standing-concerns.md")
               if not (cfg.memory_dir / name).is_file()]
    connectors = _connectors(cfg) or ["(none - local exports only)"]
    enabled = [c.id for c in concerns.load(cfg) if c.enabled]
    print("Ernest health check: ok" if not missing else "Ernest health check: degraded")
    print(f"mode: {cfg.mode}")
    print(f"profile: {cfg.profile_dir}")
    print(f"vault: {cfg.vault_dir}")
    print(f"connectors: {', '.join(connectors)}")
    print(f"active concerns: {', '.join(enabled) or '(none)'}")
    if missing:
        print(f"missing memory files: {', '.join(missing)}")
        print("fix: restore them or run `./install.sh --refresh`.")
        return 1
    issues = _diagnostics(cfg)
    if issues:
        print(f"\ndiagnostics: {len(issues)} thing(s) to improve (not fatal):")
        for problem, fix in issues:
            print(f"  - {problem}\n    fix: {fix}")
        print("\nself-repair: run `/ernest-doctor` in Claude to auto-diagnose, "
              "research missing tools, and propose fixes (approval-gated).")
    else:
        print("\ndiagnostics: all clear.")
    return 0


def cmd_onboard(cfg: config.Config, args: argparse.Namespace) -> int:
    answers = None
    if args.non_interactive:
        answers = onboard.Answers(
            name=args.name or "", role=args.role or "CEO", company=args.company or "",
            icp=args.icp or "", redlines=args.redlines or "",
        )
    result = onboard.run(cfg, answers)
    print(f"Onboarded {result.name or 'CEO'} at {result.company or '(company TBD)'}.")
    print("Next: `ernest watch` then `ernest brief`.")
    return 0


def cmd_start(cfg: config.Config, _args: argparse.Namespace) -> int:
    try:
        read_threads.run(cfg, owed_only=True)
    except ValueError:
        pass
    cards = watch.run(cfg)
    grade_run.run(cfg)
    path, summary = brief.run(cfg)
    print(summary)
    if cards:
        print(f"{len(cards)} thing(s) need attention. Details: {cfg.watch_dir}")
    print(f"Full brief: {path}")
    return 0


def cmd_watch(cfg: config.Config, _args: argparse.Namespace) -> int:
    paths = watch.run(cfg)
    if not paths:
        print("Watch: nothing slipped. No cards needed.")
        return 0
    print(f"Watch: wrote {len(paths)} card(s):")
    for path in paths:
        print(f"  - {path}")
    return 0


def cmd_brief(cfg: config.Config, _args: argparse.Namespace) -> int:
    path, summary = brief.run(cfg)
    print(summary)
    print(f"Saved: {path}")
    return 0


def cmd_draft(cfg: config.Config, args: argparse.Namespace) -> int:
    path = draft.run(cfg, concern_id=args.concern, contact=args.contact)
    if path is None:
        print("Draft: nothing to draft for that selection.")
        return 0
    print("Draft: wrote draft-only outreach (NOT sent). Review before approving a send.")
    print(f"  - {path}")
    return 0


def cmd_new_automation(cfg: config.Config, args: argparse.Namespace) -> int:
    try:
        result = automations.scaffold(
            cfg, concern_id=args.id, playbook=args.playbook,
            description=args.description or "", staleness=args.staleness,
            intent=args.intent, window=args.window,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if not result["concern_added"]:
        print(f"Concern '{args.id}' already exists; skill scaffold refreshed.")
    else:
        print(f"Registered concern '{args.id}' and scaffolded a skill.")
    print(f"  - skill: {result['skill_path']}")
    print("Run `ernest watch` to pick it up immediately.")
    return 0


def cmd_read(cfg: config.Config, args: argparse.Namespace) -> int:
    try:
        paths = read_threads.run(
            cfg,
            thread_id=args.thread,
            concern_id=args.concern,
            owed_only=args.owed or (not args.thread and not args.concern),
        )
    except ValueError as exc:
        print(f"Read: {exc}", file=sys.stderr)
        return 1
    print(f"Read: cached {len(paths)} thread(s) to 00-Threads/")
    for path in paths:
        print(f"  - {path}")
    return 0


def cmd_grade(cfg: config.Config, args: argparse.Namespace) -> int:
    both = not args.b2b and not args.talent
    paths = grade_run.run(cfg, b2b=args.b2b or both, talent=args.talent or both)
    if not paths:
        print("Grade: no leads or talent rows to grade. Add data/mail or sourcing rows.")
        return 0
    print(f"Grade: wrote {len(paths)} tier card(s), sorted Tier-1 first.")
    for path in paths:
        print(f"  - {path}")
    return 0


def cmd_audit(cfg: config.Config, args: argparse.Namespace) -> int:
    paths = audit.run(cfg, window=args.window or "365d",
                      staleness=args.staleness or "7d",
                      chunk_days=args.chunk_days)
    print(f"Audit: wrote {len(paths)} file(s) for a {args.window or '365d'} owed-reply sweep.")
    for path in paths:
        print(f"  - {path}")
    if any("audit-manifest" in p.name for p in paths):
        print("Live mail: open the manifest in Claude and run /ernest-audit — finish all chunks.")
    return 0


def cmd_learn(cfg: config.Config, args: argparse.Namespace) -> int:
    if args.note:
        learn.add_note(cfg, args.note)
    if args.adopt is not None:
        if not args.id or not args.playbook:
            print("Error: --adopt requires --id and --playbook.", file=sys.stderr)
            return 2
        try:
            result = learn.adopt(cfg, args.adopt, args.id, args.playbook,
                                 staleness=args.staleness, intent=args.intent,
                                 window=args.window)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        learn.summarize(cfg)
        print(f"Adopted proposal #{args.adopt} as concern '{result['concern_id']}'.")
        print(f"  - skill: {result['skill_path']}")
        print("Run `ernest watch` to put it to work immediately.")
        return 0
    path = learn.summarize(cfg)
    print("Learn: proposals are candidates only and need CEO approval (L2).")
    print(f"Adopt one with `ernest learn --adopt <n> --id <id> --playbook <p>`.")
    print(f"  - {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ernest", description="Ernest local-first engine.")
    parser.add_argument("--version", action="version", version=f"ernest {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("start", help="the one command: watch + brief").set_defaults(func=cmd_start)
    sub.add_parser("doctor", help="health + config snapshot").set_defaults(func=cmd_doctor)

    p_on = sub.add_parser("onboard", help="seed memory from answers")
    p_on.add_argument("--non-interactive", action="store_true")
    p_on.add_argument("--name")
    p_on.add_argument("--role")
    p_on.add_argument("--company")
    p_on.add_argument("--icp")
    p_on.add_argument("--redlines")
    p_on.set_defaults(func=cmd_onboard)

    sub.add_parser("watch", help="write remind-only cards").set_defaults(func=cmd_watch)
    sub.add_parser("brief", help="write + print the morning brief").set_defaults(func=cmd_brief)

    p_dr = sub.add_parser("draft", help="draft-only outreach")
    p_dr.add_argument("--concern")
    p_dr.add_argument("--contact")
    p_dr.set_defaults(func=cmd_draft)

    p_na = sub.add_parser("new-automation", help="register a concern + scaffold a skill")
    p_na.add_argument("--id", required=True)
    p_na.add_argument("--playbook", required=True)
    p_na.add_argument("--description")
    p_na.add_argument("--staleness")
    p_na.add_argument("--intent")
    p_na.add_argument("--window")
    p_na.set_defaults(func=cmd_new_automation)

    p_ln = sub.add_parser("learn", help="summarize / adopt self-improvement proposals")
    p_ln.add_argument("--note", help="record an observed repetition by hand")
    p_ln.add_argument("--adopt", type=int, metavar="N",
                      help="promote proposal #N into a live automation (approval step)")
    p_ln.add_argument("--id", help="concern id when adopting")
    p_ln.add_argument("--playbook", help="playbook when adopting")
    p_ln.add_argument("--staleness")
    p_ln.add_argument("--intent")
    p_ln.add_argument("--window")
    p_ln.set_defaults(func=cmd_learn)

    p_au = sub.add_parser("audit", help="deep owed-reply sweep (chunked manifest)")
    p_au.add_argument("--window", default="365d", help="lookback window (default 365d)")
    p_au.add_argument("--staleness", default="7d", help="min days waiting (default 7d)")
    p_au.add_argument("--chunk-days", type=int, default=30, dest="chunk_days",
                      help="days per MCP search bucket (default 30)")
    p_au.set_defaults(func=cmd_audit)

    p_rd = sub.add_parser("read", help="cache full thread bodies (email, Slack, etc.)")
    p_rd.add_argument("--thread", help="single thread id")
    p_rd.add_argument("--concern", help="threads from a watch concern id")
    p_rd.add_argument("--owed", action="store_true",
                      help="threads you owe a reply on (default when no --thread)")
    p_rd.set_defaults(func=cmd_read)

    p_gr = sub.add_parser("grade", help="tier inbound leads + talent against ICP rubrics")
    p_gr.add_argument("--b2b", action="store_true", help="grade B2B leads only")
    p_gr.add_argument("--talent", action="store_true", help="grade talent only")
    p_gr.set_defaults(func=cmd_grade)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = config.load()
    return args.func(cfg, args)


if __name__ == "__main__":
    raise SystemExit(main())
