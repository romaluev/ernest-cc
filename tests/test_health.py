#!/usr/bin/env python3
"""Self-healing loop: four-state doctor, safe-class heal, failure capture.

Proves the loop end-to-end in a sandbox:
  healthy audit -> snapshots taken -> deliberate breakage detected as BROKEN ->
  `heal` restores from last-good (verified, logged, evidence preserved) ->
  audit green again. Plus: rubric regeneration preserves customization,
  zero-concern files never become restore sources, crash capture writes a
  health card, and `doctor --json` is machine-readable.
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


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ernest-health-test-") as tmp:
        sandbox = Path(tmp)
        profile, vault = sandbox / "profile", sandbox / "vault"
        profile.mkdir()
        shutil.copytree(ROOT / "data", profile / "data")
        shutil.copytree(ROOT / "memory", profile / "memory")
        concerns_file = profile / "memory" / "standing-concerns.md"
        rubric = profile / "data" / "grading" / "b2b-rubric.json"

        # 1. Healthy audit: exits 0, takes last-good snapshots.
        proc = _cli(profile, vault, "doctor")
        check("healthy doctor exits 0", proc.returncode == 0)
        check("doctor names heal for self-repair", "ernest heal" in proc.stdout)
        check("doctor points to /ernest-doctor", "/ernest-doctor" in proc.stdout)
        check("diagnostics block present", "diagnostics:" in proc.stdout)
        snaps = profile / "logs" / "snapshots"
        check("last-good snapshots taken (concerns + rubrics)",
              (snaps / "standing-concerns.md").is_file() and (snaps / "b2b-rubric.json").is_file())

        # 2. doctor --json is machine-readable with the 4-state taxonomy.
        proc = _cli(profile, vault, "doctor", "--json")
        try:
            audit = json.loads(proc.stdout)
        except ValueError:
            audit = {}
        check("doctor --json parses", bool(audit))
        states = {c["state"] for c in audit.get("checks", [])}
        check("4-state taxonomy in use", states <= {"WORKING", "UNVERIFIED", "BROKEN", "OFF"} and "WORKING" in states)
        check("every check carries a remedy", all("remedy" in c for c in audit.get("checks", [])))

        # 3. Truncated-fence corruption is detected as BROKEN (the silent-off trap).
        original = concerns_file.read_text(encoding="utf-8")
        concerns_file.write_text("# Standing concerns\n```yaml\nconcerns: [broken\n", encoding="utf-8")
        proc = _cli(profile, vault, "doctor")
        check("corrupted concerns -> doctor exits 1", proc.returncode == 1)
        check("corruption surfaced as BROKEN + auto-fixable",
              "[BROKEN]" in proc.stdout and "concerns" in proc.stdout and "auto-fixable" in proc.stdout)
        check("breakage escalates to a health card",
              any((vault / "Ernest" / "00-Watch").glob("ernest-health--*.md")))

        # 4. heal restores from the last-good snapshot, verified + logged + evidence kept.
        proc = _cli(profile, vault, "heal", "--no-selftest")
        check("heal exits 0 after restore", proc.returncode == 0)
        check("heal reports fixed+verified", "fixed+verified" in proc.stdout)
        check("concerns file actually restored", "dropped-followups" in concerns_file.read_text(encoding="utf-8"))
        repairs = (profile / "logs" / "repairs.jsonl").read_text(encoding="utf-8")
        check("repair logged with verification", '"check": "concerns.parse"' in repairs and '"verified": true' in repairs)
        check("broken file preserved as evidence",
              any((profile / "logs" / "repairs").glob("standing-concerns.md@*.broken")))
        proc = _cli(profile, vault, "doctor")
        check("post-heal doctor exits 0", proc.returncode == 0)

        # 5. Deleted rubric: heal restores the snapshot (customization preserved).
        rubric.unlink()
        proc = _cli(profile, vault, "heal", "--no-selftest")
        check("rubric heal exits 0", proc.returncode == 0)
        data = json.loads(rubric.read_text(encoding="utf-8"))
        check("restored rubric keeps JSON customization (wpp)",
              "wpp" in data.get("tier1", {}).get("companies", []))

        # 6. Zero-concern file never becomes the restore source.
        good_snapshot = (snaps / "standing-concerns.md").read_text(encoding="utf-8")
        concerns_file.write_text("# Standing concerns\n```yaml\nconcerns: []\n```\n", encoding="utf-8")
        _cli(profile, vault, "doctor")
        check("empty-concern file NOT snapshotted over last-good",
              (snaps / "standing-concerns.md").read_text(encoding="utf-8") == good_snapshot)
        concerns_file.write_text(original, encoding="utf-8")

        # 7. Missing-key footgun (JSON replaces defaults wholesale) -> UNVERIFIED, not silent.
        data = json.loads(rubric.read_text(encoding="utf-8"))
        data.pop("trash", None)
        rubric.write_text(json.dumps(data), encoding="utf-8")
        proc = _cli(profile, vault, "doctor", "--json")
        audit = json.loads(proc.stdout)
        b2b = next(c for c in audit["checks"] if c["id"] == "grading.b2b")
        check("missing rubric key flagged (signals OFF warning)",
              b2b["state"] == "UNVERIFIED" and "trash" in b2b["evidence"])

        # 8. Crash capture: engine failure writes a card + repair entry, exit 1 not traceback-only.
        (profile / "data" / "grading").mkdir(exist_ok=True)
        from ernest import config as config_mod, health
        env_keep = {k: os.environ.get(k) for k in
                    ("ERNEST_PROFILE_DIR", "ERNEST_LOCAL_VAULT", "ERNEST_MODE", "ERNEST_TODAY")}
        os.environ.update({"ERNEST_PROFILE_DIR": str(profile), "ERNEST_LOCAL_VAULT": str(vault),
                           "ERNEST_MODE": "local", "ERNEST_TODAY": "2026-06-25"})
        try:
            cfg = config_mod.load()
            health.record_failure(cfg, "watch", RuntimeError("synthetic crash"))
        finally:
            for k, v in env_keep.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        card = vault / "Ernest" / "00-Watch" / "ernest-health--2026-06-25.md"
        check("crash captured to health card", card.is_file() and "synthetic crash" in card.read_text(encoding="utf-8"))
        repairs = (profile / "logs" / "repairs.jsonl").read_text(encoding="utf-8")
        check("crash captured to repairs log", '"check": "crash.watch"' in repairs)

    if FAILURES:
        print(f"FAIL - self-healing loop ({FAILURES} failure(s))")
        return 1
    print("PASS - self-healing loop: detect -> heal -> verify -> escalate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
