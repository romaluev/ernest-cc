#!/usr/bin/env python3
"""Self-improving loop v2: typed capture -> evidence-ranked proposals ->
versioned apply -> measured -> rollback.

Proves in a sandbox:
  correction classification (claude-reflect classes); 3x tier-corrections group
  into one READY rubric_add whose apply actually changes `ernest grade` behavior
  and whose rollback restores it (snapshot + applied.jsonl trail); noise
  complaints propose a staleness bump applied in standing-concerns.md;
  preference signals propose an engine-settings change; dead concerns surface
  from telemetry; post-apply regressions auto-propose their own rollback;
  recurring repairs demand a durable fix.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILURES = 0


def check(label: str, cond: bool) -> None:
    global FAILURES
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label}")
    if not cond:
        FAILURES += 1


def _cli(profile: Path, vault: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update({"ERNEST_PROFILE_DIR": str(profile), "ERNEST_LOCAL_VAULT": str(vault),
                "ERNEST_MODE": "local", "ERNEST_TODAY": "2026-06-25",
                "ERNEST_NO_RENDER": "1", "PYTHONPATH": str(ROOT)})
    return subprocess.run([sys.executable, "-m", "ernest.cli", *args],
                          capture_output=True, text=True, env=env, cwd=str(ROOT))


def main() -> int:  # noqa: PLR0915 — one linear scenario, deliberately
    from ernest import learn

    # 0. Correction classes classify as designed (claude-reflect patterns).
    check("classify: tier correction", learn.classify("Apex was actually tier-1") == "rubric_correction")
    check("classify: noise complaint", learn.classify("dropped-followups is too noisy, false positives")
          == "threshold_complaint")
    check("classify: missed item", learn.classify("you missed the Apex Bank thread") == "missed_item")
    check("classify: preference", learn.classify("answers are too long, prefer pdf") == "preference")
    check("classify: repetition", learn.classify("I keep manually checking Korea list") == "new_use_case")
    check("classify: none", learn.classify("great, thanks") is None)

    with tempfile.TemporaryDirectory(prefix="ernest-learn2-") as tmp:
        sandbox = Path(tmp)
        profile, vault = sandbox / "profile", sandbox / "vault"
        profile.mkdir()
        shutil.copytree(ROOT / "data", profile / "data")
        shutil.copytree(ROOT / "memory", profile / "memory")

        env_keep = dict(os.environ)
        os.environ.update({"ERNEST_PROFILE_DIR": str(profile), "ERNEST_LOCAL_VAULT": str(vault),
                           "ERNEST_MODE": "local", "ERNEST_TODAY": "2026-06-25"})
        try:
            from ernest import concerns, config as config_mod, grading, improve, telemetry
            cfg = config_mod.load()

            # 1. Three tier corrections -> ONE grouped READY proposal with a diff.
            for note in ("Acme Robotics was actually tier-1",
                         "you graded Acme Robotics tier-2 but Acme Robotics is actually tier-1",
                         "again: Acme Robotics was actually tier-1"):
                _cli(profile, vault, "feedback", note)
            props = improve.generate(cfg)
            rubric = next((p for p in props if p["kind"] == "rubric_add"), None)
            check("3 corrections -> one rubric_add proposal", rubric is not None)
            check("grouped evidence == 3", rubric and rubric["evidence_count"] == 3)
            check("proposal READY at threshold 3", bool(rubric and rubric["ready"]))
            check("proposal carries diff + reverse", bool(rubric and rubric["diff"] and rubric["reverse"]))

            # 2. Apply changes real grading behavior; versioned + logged.
            before = grading.grade_b2b(company="Acme Robotics", text="intro", cfg=cfg)
            check("before apply: tier-2 default", before.tier == "tier-2")
            proc = _cli(profile, vault, "learn", "--apply", str(rubric["key"]))
            check("apply exits 0 (selftest-gated)", proc.returncode == 0)
            after = grading.grade_b2b(company="Acme Robotics", text="intro", cfg=cfg)
            check("after apply: tier-1 (behavior changed)", after.tier == "tier-1")
            applied = [json.loads(l) for l in
                       (profile / "logs" / "applied.jsonl").read_text(encoding="utf-8").splitlines()]
            apply_entry = next(e for e in applied if e["action"] == "apply")
            check("apply logged with snapshot + selftest pass",
                  apply_entry.get("snapshot") and apply_entry.get("selftest") == "pass")
            check("version snapshot exists",
                  any((profile / "logs" / "versions").glob("b2b-rubric.json@*")))

            # 3. Rollback restores prior behavior.
            proc = _cli(profile, vault, "learn", "--rollback", str(apply_entry["id"]))
            check("rollback exits 0", proc.returncode == 0)
            restored = grading.grade_b2b(company="Acme Robotics", text="intro", cfg=cfg)
            check("after rollback: tier-2 again", restored.tier == "tier-2")

            # 4. Noise complaints -> staleness bump proposal; applying edits the concern.
            for _ in range(3):
                _cli(profile, vault, "feedback", "dropped-followups is too noisy, false positives")
            props = improve.generate(cfg)
            tune = next((p for p in props if p["kind"] == "threshold_tune"), None)
            check("noise complaints -> threshold_tune", tune is not None and tune["ready"])
            check("tune targets staleness 7d -> 10d",
                  tune and tune["diff"]["from"] == "7d" and tune["diff"]["to"] == "10d")
            proc = _cli(profile, vault, "learn", "--apply", str(tune["key"]))
            check("tune apply exits 0", proc.returncode == 0)
            dropped = next(c for c in concerns.load(cfg) if c.id == "dropped-followups")
            check("standing-concerns staleness now 10d",
                  dropped.params.get("staleness", "").strip('"') == "10d")

            # 5. Preference signal -> engine-settings proposal -> applied to preferences.md.
            _cli(profile, vault, "feedback", "prefer pdf for the digest")
            props = improve.generate(cfg)
            pref = next((p for p in props if p["kind"] == "preference"), None)
            check("preference proposal generated (L1: 1 signal is enough)",
                  pref is not None and pref["ready"])
            proc = _cli(profile, vault, "learn", "--apply", str(pref["key"]))
            from ernest import preferences
            check("preferences.md engine setting updated",
                  preferences.load(cfg).get("read_more_format") == "pdf")

            # 6. Dead concern via telemetry -> disable_stale proposal.
            usage = profile / "logs" / "usage.jsonl"
            with usage.open("a", encoding="utf-8") as fh:
                for day in ("2026-05-01", "2026-05-08", "2026-05-15", "2026-05-20", "2026-05-24"):
                    fh.write(json.dumps({"at": f"{day}T08:00:00Z", "day": day, "cmd": "watch",
                                         "concerns": {"press-list-sync": 0}}) + "\n")
            props = improve.generate(cfg)
            stale = next((p for p in props if p["kind"] == "disable_stale"), None)
            check("dead concern -> disable_stale proposal", stale is not None)

            # 7. Post-apply regression -> auto rollback proposal (backtrack pattern).
            for _ in range(2):
                _cli(profile, vault, "feedback", "dropped-followups still too noisy, false positives")
            props = improve.generate(cfg)
            rb = next((p for p in props if p["kind"] == "rollback"), None)
            check("2 post-apply complaints -> rollback proposal", rb is not None)

            # 8. Recurring repairs -> make_stick.
            with (profile / "logs" / "repairs.jsonl").open("a", encoding="utf-8") as fh:
                for _ in range(3):
                    fh.write(json.dumps({"at": "2026-06-20T00:00:00Z", "check": "concerns.parse",
                                         "action": "auto-fix", "verified": True}) + "\n")
            props = improve.generate(cfg)
            check("3x same repair -> make_stick proposal",
                  any(p["kind"] == "make_stick" for p in props))

            # 9. The learn report carries the typed sections.
            proc = _cli(profile, vault, "learn")
            summary = (profile / "logs" / "learning-summary.md").read_text(encoding="utf-8")
            check("report has typed-proposals section", "Typed proposals (evidence-ranked)" in summary)
            check("report has measurement section", "Applied changes & measurement" in summary)
            check("report marks rollback command", "--rollback" in summary)
        finally:
            os.environ.clear()
            os.environ.update(env_keep)

    if FAILURES:
        print(f"FAIL - self-improving loop v2 ({FAILURES} failure(s))")
        return 1
    print("PASS - self-improving loop: capture -> propose -> apply -> measure -> rollback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
