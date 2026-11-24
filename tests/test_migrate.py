#!/usr/bin/env python3
"""Adopting an earlier install must not lose or invent anything.

The expensive failure this guards is subtle: a fresh `install.sh` writes the
SAMPLE world with a brand-new mtime, so a naive newer-wins merge lets
placeholder identity beat the user's real memory — a clean-looking install that
silently threw away who they are and everything the system had learned.

  1. A source checkout is not a profile (adopting one imports placeholders).
  2. Shipped sample content never outranks real user content.
  3. A file the user edited in the target IS preserved.
  4. Append-only history is unioned, deduped, and never truncated.
  5. Secrets are never merged — copied only into an empty slot, 0600.
  6. The onboarded marker is re-derived, and refused for a sample-world source.
  7. Idempotent: a second run adopts nothing.
  8. Nothing is deleted from either side, and a backup exists.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import migrate  # noqa: E402

FAILURES = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global FAILURES
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES += 1


def _profile(path: Path, company: str, *, logs: dict | None = None,
             secrets: bool = False) -> Path:
    (path / "memory").mkdir(parents=True, exist_ok=True)
    (path / "logs").mkdir(parents=True, exist_ok=True)
    (path / "ernest.yaml").write_text("scope:\n  read: []\n", encoding="utf-8")
    (path / "memory" / "company-core.md").write_text(
        f"# Company Core\n\n- Company: {company}\n", encoding="utf-8")
    for name, lines in (logs or {}).items():
        (path / "logs" / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    if secrets:
        (path / "env").write_text("SECRET=from-old\n", encoding="utf-8")
    return path


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        os.environ["ERNEST_LOCAL_VAULT"] = str(tmp / "vault")

        # 1. The repo checkout must never be treated as an adoptable profile.
        check("the source checkout is recognized as a checkout",
              migrate.is_source_checkout(ROOT))
        check("the source checkout is NOT a profile", not migrate.is_profile(ROOT))

        old = _profile(tmp / "old", "RealCo Inc",
                       logs={"feedback.jsonl": ['{"at":"1","note":"a"}',
                                                '{"at":"2","note":"b"}'],
                             "applied.jsonl": ['{"id":"A1"}']},
                       secrets=True)
        (old / "data" / "grading").mkdir(parents=True)
        (old / "data" / "grading" / "b2b-rubric.json").write_text(
            '{"tier1":{"companies":["tuned"]}}', encoding="utf-8")

        # A target that looks exactly like a fresh install: shipped sample memory,
        # written just now, plus one pre-existing history entry.
        new = tmp / "new"
        (new / "memory").mkdir(parents=True)
        (new / "logs").mkdir(parents=True)
        (new / "ernest.yaml").write_text("scope:\n  read: []\n", encoding="utf-8")
        shutil.copy2(ROOT / "memory" / "company-core.md", new / "memory" / "company-core.md")
        (new / "logs" / "feedback.jsonl").write_text('{"at":"2","note":"b"}\n', encoding="utf-8")

        res = migrate.migrate(new, old, pristine_root=ROOT)
        check("migration succeeds", res["ok"], str(res.get("why")))
        check("a backup was taken first", bool(res["backup"]) and Path(res["backup"]).is_dir())

        # 2. Sample content loses to real content, despite a newer mtime.
        core = (new / "memory" / "company-core.md").read_text(encoding="utf-8")
        check("real identity replaced the shipped sample", "RealCo Inc" in core, core[:60])
        check("tuned rubric came across",
              "tuned" in (new / "data" / "grading" / "b2b-rubric.json").read_text(encoding="utf-8"))

        # 4. History is unioned and deduped, never truncated.
        fb = [l for l in (new / "logs" / "feedback.jsonl").read_text(encoding="utf-8").splitlines() if l]
        check("history is unioned", len(fb) == 2, str(fb))
        check("history is deduped", len(set(fb)) == len(fb))
        check("pre-existing history survived", '{"at":"2","note":"b"}' in fb)
        check("rollback history came across", (new / "logs" / "applied.jsonl").is_file())

        # 5. Secrets: copied into an empty slot, owner-only.
        check("secret copied into an empty slot", (new / "env").is_file())
        check("secret is owner-only", oct((new / "env").stat().st_mode)[-3:] == "600",
              oct((new / "env").stat().st_mode)[-3:])
        (new / "env").write_text("SECRET=mine\n", encoding="utf-8")
        migrate.migrate(new, old, pristine_root=ROOT)
        check("an existing secret is never overwritten",
              "mine" in (new / "env").read_text(encoding="utf-8"))

        # 6. The onboarded marker is derived, not copied.
        check("onboarded marker written for a real profile",
              (Path(os.environ["ERNEST_LOCAL_VAULT"]) / ".onboarded").is_file())

        # 3. A file the user edited in the target is preserved.
        (new / "memory" / "company-core.md").write_text(
            "# Company Core\n\n- Company: EditedHere\n", encoding="utf-8")
        migrate.migrate(new, old, pristine_root=ROOT)
        check("a user-edited target file is not clobbered",
              "EditedHere" in (new / "memory" / "company-core.md").read_text(encoding="utf-8"))

        # 7. Idempotent.
        again = migrate.migrate(new, old, pristine_root=ROOT)
        counts = [a["count"] for a in again["adopted"]]
        check("a second run adopts nothing", sum(counts) == 0, str(again["adopted"]))

        # 8. Nothing is removed from the source.
        check("the source is left intact",
              (old / "memory" / "company-core.md").is_file() and (old / "env").is_file())

        # 6b. A sample-world source must not claim onboarded.
        os.environ["ERNEST_LOCAL_VAULT"] = str(tmp / "vault2")
        sample = _profile(tmp / "sample", "x")
        shutil.copy2(ROOT / "memory" / "company-core.md", sample / "memory" / "company-core.md")
        fresh = tmp / "fresh"
        (fresh / "memory").mkdir(parents=True)
        (fresh / "ernest.yaml").write_text("scope:\n", encoding="utf-8")
        migrate.migrate(fresh, sample, pristine_root=ROOT)
        check("no onboarded marker claimed for a sample-world source",
              not (Path(os.environ["ERNEST_LOCAL_VAULT"]) / ".onboarded").exists())

        # Same-profile guard.
        check("migrating a profile onto itself is refused",
              migrate.migrate(new, new, pristine_root=ROOT)["ok"] is False)

    if FAILURES:
        print(f"FAIL - migrate ({FAILURES} failure(s))")
        return 1
    print("PASS - migrate: sample loses to real, edits preserved, history unioned, secrets safe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
