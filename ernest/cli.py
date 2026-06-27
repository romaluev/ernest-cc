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
    ernest render [--open] [--pdf]      clean, consistent digest of today (read more)
    ernest feedback "..."             record what to change about answers/work
    ernest prefs                       show current engine preferences

Local-first: every command works with no VPS and no live connectors, reading
exported data under `data/`. Nothing here ever sends.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__, config
from . import (automations, audit, brief, concerns, connect, draft, feedback,
               grade_run, learn, onboard, preferences, read_threads, render, watch)


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
    cst = concerns.status(cfg)
    enabled = [c.id for c in concerns.load(cfg) if c.enabled]
    degraded = bool(missing) or cst.level == "error"
    print("Ernest health check: ok" if not degraded else "Ernest health check: degraded")
    print(f"mode: {cfg.mode}")
    print(f"profile: {cfg.profile_dir}")
    print(f"vault: {cfg.vault_dir}")
    print(f"connectors: {', '.join(connectors)}")
    if cfg.mode == "vps":
        url = connect.resolve_url(cfg)
        if not url:
            print("brain: vps mode but no brain URL set — run /ernest-connect-brain or go local")
        else:
            ok, detail = connect.health_probe(url)
            print(f"brain: reachable ({detail}) — {url}" if ok
                  else f"brain: OFFLINE — {url} ({detail}); running on local fallback")
    onboarded = (cfg.vault_dir / ".onboarded").is_file()
    print(f"onboarded: {'yes' if onboarded else 'no — running on SAMPLE data; run /ernest-setup to personalize'}")
    print(f"active concerns: {', '.join(enabled) or '(none)'}")
    if cst.level != "ok":
        marker = "ERROR" if cst.level == "error" else "note"
        print(f"watch concerns [{marker}]: {cst.message}")
    if missing:
        print(f"missing memory files: {', '.join(missing)}")
        print("fix: restore them or run `./install.sh --refresh`.")
        return 1
    if cst.level == "error":
        print("fix: your watch reminders are OFF. Tell Ernest to repair standing-concerns, "
              "or run `/ernest-onboard` / setup again.")
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


def cmd_connect_brain(cfg: config.Config, args: argparse.Namespace) -> int:
    return connect.connect(cfg, args.url or "", name=args.name, token_env=args.token_env)


def cmd_go_local(cfg: config.Config, args: argparse.Namespace) -> int:
    return connect.go_local(cfg, name=args.name)


def cmd_update(cfg: config.Config, args: argparse.Namespace) -> int:
    import os
    import subprocess
    from pathlib import Path
    src = os.environ.get("ERNEST_SRC_DIR", "").strip()
    action = getattr(args, "action", None) or "apply"
    if not src or not (Path(src) / ".git").exists():
        print("Auto-update needs the Ernest source checkout (a git clone of ernest-core).")
        print("The installer records it as ERNEST_SRC_DIR; set it, or run")
        print("  scripts/self-update.sh", action, "from that checkout directly.")
        return 1
    script = Path(src) / "scripts" / "self-update.sh"
    if not script.is_file():
        print(f"self-update.sh not found at {script}")
        return 1
    return subprocess.run(["bash", str(script), action]).returncode


def cmd_concern_toggle(cfg: config.Config, args: argparse.Namespace) -> int:
    enabled = args._enable
    ok = concerns.set_enabled(cfg, args.id, enabled)
    if ok:
        print(f"{'Enabled' if enabled else 'Disabled'} concern '{args.id}'."
              + ("" if enabled else " It will stop producing reminders until re-enabled."))
        return 0
    print(f"No concern called '{args.id}'. See active ones with `ernest doctor`.")
    return 1


def cmd_schedule(cfg: config.Config, args: argparse.Namespace) -> int:
    """Install the daily morning brief + update check so Ernest runs on its own."""
    import sys
    import subprocess
    from pathlib import Path
    bin_path = cfg.profile_dir / "bin" / "ernest"
    logs = cfg.profile_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    if sys.platform != "darwin":
        print("On this OS, scheduling uses cron. Install the bundled schedule with:")
        print(f"  crontab {cfg.profile_dir}/crontab.example")
        print("(weekday 08:00 brief, 11:00/16:00 watch, daily 07:30 update check)")
        return 0
    la = Path.home() / "Library" / "LaunchAgents"
    la.mkdir(parents=True, exist_ok=True)
    jobs = [
        ("com.notiky.ernest.brief", f'"{bin_path}" start', 8, 0),
        ("com.notiky.ernest.update", f'"{bin_path}" update check', 7, 30),
    ]
    remove = getattr(args, "remove", False)
    for label, cmdline, hour, minute in jobs:
        plist = la / f"{label}.plist"
        subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
        if remove:
            try:
                plist.unlink()
            except FileNotFoundError:
                pass
            continue
        plist.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0"><dict>\n'
            f'  <key>Label</key><string>{label}</string>\n'
            '  <key>ProgramArguments</key>\n'
            f'  <array><string>/bin/zsh</string><string>-lc</string><string>{cmdline}</string></array>\n'
            f'  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>{hour}</integer>'
            f'<key>Minute</key><integer>{minute}</integer></dict>\n'
            f'  <key>StandardOutPath</key><string>{logs}/launchd.log</string>\n'
            f'  <key>StandardErrorPath</key><string>{logs}/launchd.err</string>\n'
            '</dict></plist>\n', encoding="utf-8")
        subprocess.run(["launchctl", "load", str(plist)], capture_output=True)
    if remove:
        print("Removed Ernest's morning schedule.")
    else:
        print("Done — Ernest will check your morning brief at 8:00 and look for updates at 7:30, every day.")
        print("Nothing is sent; it only prepares what needs you. Remove anytime with `ernest schedule --remove`.")
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
    prefs = preferences.load(cfg)
    auto_render = preferences.truthy(prefs.get("auto_render", "on")) and not os.environ.get("ERNEST_NO_RENDER")
    digest = render.run(cfg) if auto_render else None
    cst = concerns.status(cfg)
    if cst.level == "error":
        print(f"⚠ Watch reminders are OFF — {cst.message}")
        print("  (So 'nothing needs you' below may be wrong.) Ask Ernest to fix your standing concerns.")
    print(summary)
    if cards:
        print(f"{len(cards)} thing(s) need attention. Details: {cfg.watch_dir}")
    print(f"Full brief: {path}")
    if digest:
        print(f"Read more (clean digest): {digest}")
    if not (cfg.vault_dir / ".onboarded").is_file():
        print("\nℹ This is SAMPLE data (placeholder company/people). Run `/ernest-setup` "
              "(or `ernest onboard`) to make it yours — then it's your real inbox/CRM.")
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


def cmd_render(cfg: config.Config, args: argparse.Namespace) -> int:
    path = render.run(cfg)
    print(f"Render: wrote a consistent HTML digest.\n  - {path}")
    want_pdf = args.pdf or preferences.load(cfg).get("read_more_format", "html").lower() == "pdf"
    if want_pdf:
        pdf = render.to_pdf(path)
        if pdf:
            print(f"  - {pdf}")
            path = pdf
        else:
            print("  - PDF tool not found; open the HTML and use Print -> Save as PDF.")
    if args.open:
        if render.open_in_browser(path):
            print("Opened in your browser.")
        else:
            print(f"Open it manually: {path}")
    else:
        print("Open it in a browser, or run `ernest render --open`.")
    return 0


def cmd_feedback(cfg: config.Config, args: argparse.Namespace) -> int:
    note = " ".join(args.note).strip()
    if not note:
        print("Tell me what to change, e.g. `ernest feedback \"answers too long\"`.")
        return 2
    feedback.record(cfg, note)
    print("Noted. I logged your feedback and will fold it into how I work.")
    print(f"  - log: {feedback.log_path(cfg)}")
    print("  - lasting preferences live in memory/preferences.md (ask me to update them).")
    return 0


def cmd_prefs(cfg: config.Config, args: argparse.Namespace) -> int:
    prefs = preferences.load(cfg)
    print("Current engine preferences:")
    for key, val in prefs.items():
        print(f"  - {key}: {val}")
    print(f"Edit the narrative + settings in {cfg.memory_dir / 'preferences.md'}.")
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
    wd, cold = audit.resolve_window_days(cfg, args.window or "")
    paths = audit.run(cfg, window=args.window or "",
                      staleness=args.staleness or "7d",
                      chunk_days=args.chunk_days)
    kind = "first-time 12-month" if cold else f"incremental {wd}d (since last sweep)"
    print(f"Sweep: wrote {len(paths)} file(s) for a {kind} owed-reply sweep across all tools.")
    for path in paths:
        print(f"  - {path}")
    if any("audit-manifest" in p.name for p in paths):
        print("Live: open the manifest in Claude and run /ernest-audit — search every tool, "
              "cross-check for resolution, finish all chunks.")
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

    p_cb = sub.add_parser("connect-brain", help="point this surface at the VPS brain (shared memory/cards)")
    p_cb.add_argument("--url", help="brain URL, e.g. https://brain.example.com (else env/persisted)")
    p_cb.add_argument("--name", default=connect.DEFAULT_NAME, help="MCP server name (default ernest-brain)")
    p_cb.add_argument("--token-env", default=connect.DEFAULT_TOKEN_ENV, dest="token_env",
                      help="env var holding the bearer token (default ERNEST_BRAIN_TOKEN)")
    p_cb.set_defaults(func=cmd_connect_brain)

    p_gl = sub.add_parser("go-local", help="disconnect the brain; run local-only")
    p_gl.add_argument("--name", default=connect.DEFAULT_NAME, help="MCP server name to remove")
    p_gl.set_defaults(func=cmd_go_local)

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
    p_au.add_argument("--window", default="", help="lookback window; default = 12mo on first sweep, then incremental since last sweep")
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

    p_re = sub.add_parser("render", help="clean, consistent HTML digest of today")
    p_re.add_argument("--open", action="store_true", help="open the digest in a browser")
    p_re.add_argument("--pdf", action="store_true", help="also export a PDF (best-effort)")
    p_re.set_defaults(func=cmd_render)

    p_fb = sub.add_parser("feedback", help="tell Ernest what to change about its answers/work")
    p_fb.add_argument("note", nargs="*", help="free text, e.g. \"answers too long\"")
    p_fb.set_defaults(func=cmd_feedback)

    p_pf = sub.add_parser("prefs", help="show current engine preferences")
    p_pf.set_defaults(func=cmd_prefs)

    p_dis = sub.add_parser("disable-concern", help="turn off an automation (rollback)")
    p_dis.add_argument("id")
    p_dis.set_defaults(func=cmd_concern_toggle, _enable=False)
    p_en = sub.add_parser("enable-concern", help="turn an automation back on")
    p_en.add_argument("id")
    p_en.set_defaults(func=cmd_concern_toggle, _enable=True)

    p_sch = sub.add_parser("schedule", help="run the morning brief + update check automatically (launchd/cron)")
    p_sch.add_argument("--remove", action="store_true", help="remove the schedule")
    p_sch.set_defaults(func=cmd_schedule)

    p_up = sub.add_parser("update", help="safe auto-update from GitHub (validate + rollback)")
    p_up.add_argument("action", nargs="?", choices=["check", "apply", "auto", "status"],
                      default="apply", help="default: apply (one-tap)")
    p_up.set_defaults(func=cmd_update)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = config.load()
    return args.func(cfg, args)


if __name__ == "__main__":
    raise SystemExit(main())
