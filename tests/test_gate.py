#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ernest import gate  # noqa: E402

FAILURES: list[str] = []


def check(label: str, condition: bool) -> None:
    print(f"  [{'ok  ' if condition else 'FAIL'}] {label}")
    if not condition:
        FAILURES.append(label)


def test_live_connector_mutations_are_blocked() -> None:
    for tool in [
        "mcp__gmail__send_email",
        "mcp__outlook__reply",
        "mcp__slack__post_message",
        "mcp__hubspot__update_contact",
        "mcp__google_calendar__create_event",
        "send_email",
    ]:
        check(f"blocks {tool}", gate.draft_only_block(tool, {}, str(ROOT)) is not None)


def test_reads_and_drafts_are_allowed() -> None:
    for tool in [
        "mcp__gmail__search_threads",
        "mcp__gmail__create_draft",
        "mcp__hubspot__list_contacts",
        "mcp__ernest-brain__search_mail",
        "Read",
    ]:
        check(f"allows {tool}", gate.draft_only_block(tool, {}, str(ROOT)) is None)


def test_filesystem_scope_blocks_self_modification_and_secrets() -> None:
    scope = gate.load_scope(str(ROOT))
    check("scope loaded", scope is not None)
    if scope is None:
        return

    blocked = [
        ("Write", "CLAUDE.md"),
        ("Write", "hooks/gate.py"),
        ("Write", "skills/ernest-watch/SKILL.md"),
        ("Read", ".env"),
        ("Read", "secrets.txt"),
        ("Write", "../../etc/passwd"),
    ]
    allowed = [
        ("Write", "memory/company-core.md"),
        ("Write", "logs/run.log"),
        ("Read", "CLAUDE.md"),
        ("Read", "skills/ernest-watch/SKILL.md"),
    ]

    for tool, path in blocked:
        check(f"scope blocks {tool} {path}", gate.scope_block(scope, tool, {"file_path": path}, str(ROOT)) is not None)
    for tool, path in allowed:
        check(f"scope allows {tool} {path}", gate.scope_block(scope, tool, {"file_path": path}, str(ROOT)) is None)


def test_shell_escape_to_live_external_action_is_blocked() -> None:
    block = gate.shell_block(
        "Bash",
        {"command": "curl -X POST https://slack.com/api/chat.postMessage -d text=hi"},
    )
    check("blocks Bash live Slack post", block is not None)


def test_vault_writes_are_allowed_only_inside_vault() -> None:
    vault = tempfile.mkdtemp(prefix="ernest_vault_")
    os.environ["ERNEST_LOCAL_VAULT"] = vault
    scope = gate.load_scope(str(ROOT))
    check("vault scope loaded", scope is not None)
    if scope is None:
        return

    check("allows write inside vault", gate.scope_block(
        scope,
        "Write",
        {"file_path": os.path.join(vault, "Ernest/00-Watch/card.md")},
        str(ROOT),
    ) is None)
    check("blocks write outside vault", gate.scope_block(
        scope,
        "Write",
        {"file_path": "/tmp/not-ernest-vault/card.md"},
        str(ROOT),
    ) is not None)


def test_hubspot_hygiene_exception_requires_full_arming() -> None:
    root = Path(tempfile.mkdtemp(prefix="ernest_gate_")) / "profile"
    logs = root / "logs"
    logs.mkdir(parents=True)
    (root / "ernest.yaml").write_text(
        "hygiene_policy:\n"
        "  job_id: ernest-hubspot-hygiene\n"
        "  dry_run: false\n"
        "  approved: true\n"
        "  active_run_marker: logs/hygiene-active-run.json\n"
        "  mechanical_fields:\n"
        "    - company\n    - firstname\n    - lastname\n    - jobtitle\n",
        encoding="utf-8",
    )
    (logs / "hygiene-active-run.json").write_text(
        json.dumps(
            {
                "job_id": "ernest-hubspot-hygiene",
                "mechanical_only": True,
                "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        ),
        encoding="utf-8",
    )

    gate._hygiene_policy_cache = None
    os.environ["ERNEST_CRON_JOB"] = "ernest-hubspot-hygiene"
    check("hygiene armed allows mechanical update", gate.hygiene_may_auto_apply(
        "mcp__hubspot__update_contact",
        {"properties": {"company": "Acme"}},
        str(root),
    ))
    check("draft gate lets armed hygiene pass", gate.draft_only_block(
        "mcp__hubspot__update_contact",
        {"properties": {"company": "Acme"}},
        str(root),
    ) is None)

    gate._hygiene_policy_cache = None
    os.environ["ERNEST_CRON_JOB"] = "ernest-ambient-watch"
    check("wrong cron blocks hygiene", not gate.hygiene_may_auto_apply(
        "mcp__hubspot__update_contact",
        {"properties": {"company": "Acme"}},
        str(root),
    ))


def test_pre_tool_use_hook_outputs_deny_for_live_send() -> None:
    payload = {
        "tool_name": "mcp__gmail__send_email",
        "tool_input": {"to": "x@example.com", "body": "hi"},
    }
    proc = subprocess.run(
        [sys.executable, str(ROOT / "hooks" / "pre_tool_use.py")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(ROOT),
        check=False,
    )
    check("hook process exits 0", proc.returncode == 0)
    if proc.returncode != 0:
        print(proc.stderr)
        return
    decision = json.loads(proc.stdout)
    check("hook denies live send", decision["hookSpecificOutput"]["permissionDecision"] == "deny")
    check("hook explains draft-only", "ERNEST DRAFT ONLY" in decision["hookSpecificOutput"]["permissionDecisionReason"])


if __name__ == "__main__":
    test_live_connector_mutations_are_blocked()
    test_reads_and_drafts_are_allowed()
    test_filesystem_scope_blocks_self_modification_and_secrets()
    test_shell_escape_to_live_external_action_is_blocked()
    test_vault_writes_are_allowed_only_inside_vault()
    test_hubspot_hygiene_exception_requires_full_arming()
    test_pre_tool_use_hook_outputs_deny_for_live_send()
    if FAILURES:
        print(f"FAILED {len(FAILURES)} checks:")
        for failure in FAILURES:
            print(f"  - {failure}")
        raise SystemExit(1)
    print("PASS - all gate checks held")
