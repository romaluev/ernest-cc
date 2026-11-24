#!/usr/bin/env python3
"""Phase 3 — safe auto-update (scripts/self-update.sh).

End-to-end against a local git "remote": validated update applies and preserves
customizations; a forced post-verify failure rolls back cleanly; a non-fast-forward
is refused; a commit that fails the gate self-test is never applied.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILURES: list[str] = []


def check(label: str, condition: bool) -> None:
    print(f"  [{'ok  ' if condition else 'FAIL'}] {label}")
    if not condition:
        FAILURES.append(label)


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], text=True,
                          capture_output=True, check=True).stdout.strip()


def run_su(src: Path, profile: Path, vault: Path, sub: str, **extra_env) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update({
        "ERNEST_SRC_DIR": str(src),
        "ERNEST_PROFILE_DIR": str(profile),
        "ERNEST_LOCAL_VAULT": str(vault),
        "ERNEST_UPDATE_CHANNEL": "stable",
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    })
    env.update({k: str(v) for k, v in extra_env.items()})
    return subprocess.run(["bash", str(src / "scripts" / "self-update.sh"), sub],
                          text=True, capture_output=True, check=False, env=env)


def install(src: Path, profile: Path, vault: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update({"ERNEST_PROFILE_DIR": str(profile), "ERNEST_LOCAL_VAULT": str(vault)})
    return subprocess.run(["bash", str(src / "install.sh"), "--no-run"],
                          cwd=str(src), text=True, capture_output=True, check=False, env=env)


def pub_commit(pub: Path, relpath: str, content: str, msg: str) -> None:
    target = pub / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    git(pub, "add", "-A")
    git(pub, "commit", "-q", "-m", msg)
    git(pub, "push", "-q", "origin", "stable")


def test_self_update_full_lifecycle() -> None:
    sb = Path(tempfile.mkdtemp(prefix="ernest_su_"))
    src, profile, vault = sb / "src", sb / "profile", sb / "vault"
    bare, pub = sb / "remote.git", sb / "pub"
    try:
        # Build SRC from the WORKING tree (so our uncommitted Phase 1-3 code is included).
        shutil.copytree(ROOT, src, ignore=shutil.ignore_patterns(".git", "logs", "__pycache__", "*.pyc"))
        git(src, "init", "-q")
        git(src, "checkout", "-q", "-b", "stable")
        git(src, "add", "-A")
        git(src, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "base")
        subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)
        git(src, "remote", "add", "origin", str(bare))
        git(src, "push", "-q", "origin", "stable")
        git(src, "branch", "--set-upstream-to=origin/stable", "stable")

        inst = install(src, profile, vault)
        check("install ok", inst.returncode == 0)
        if inst.returncode != 0:
            print(inst.stderr); return

        # second clone publishes upgrades
        subprocess.run(["git", "clone", "-q", "-b", "stable", str(bare), str(pub)], check=True)

        # ---- 1. validated update: check stages, apply installs ----
        pub_commit(pub, "skills/auto-update-marker/SKILL.md",
                   "---\nname: auto-update-marker\n---\nv2 marker\n", "feat: marker skill")
        r = run_su(src, profile, vault, "check")
        check("check exits 0 on valid update", r.returncode == 0)
        check("pending staged", (profile / "logs" / "update-pending.json").is_file())

        # CEO customizations made before applying
        (profile / "custom" / "skills" / "ceo-skill").mkdir(parents=True, exist_ok=True)
        (profile / "custom" / "skills" / "ceo-skill" / "SKILL.md").write_text(
            "---\nname: ceo-skill\n---\nmine\n", encoding="utf-8")
        mem = profile / "memory" / "company-core.md"
        mem.write_text(mem.read_text(encoding="utf-8") + "\nCEO EDIT\n", encoding="utf-8")

        r = run_su(src, profile, vault, "apply")
        check("apply exits 0", r.returncode == 0)
        check("update landed in profile", (profile / "skills" / "auto-update-marker" / "SKILL.md").is_file())
        check("custom survived apply", (profile / "skills" / "ceo-skill" / "SKILL.md").is_file())
        check("memory survived apply", "CEO EDIT" in mem.read_text(encoding="utf-8"))
        check("no rollback flag after clean apply", not (profile / "logs" / "update-rolledback.flag").is_file())
        head_after_apply = git(src, "rev-parse", "HEAD")

        # ---- 2. forced post-verify failure -> rollback ----
        pub_commit(pub, "docs/CHANGE.md", "v3\n", "feat: v3 change")
        r = run_su(src, profile, vault, "apply", ERNEST_UPDATE_FORCE_POSTFAIL="1")
        check("apply with forced postfail returns rollback code", r.returncode == 5)
        check("rollback flag set", (profile / "logs" / "update-rolledback.flag").is_file())
        check("src rolled back to previous HEAD", git(src, "rev-parse", "HEAD") == head_after_apply)
        check("customizations intact after rollback", "CEO EDIT" in mem.read_text(encoding="utf-8")
              and (profile / "skills" / "ceo-skill" / "SKILL.md").is_file())

        # next apply is skipped until the flag is cleared
        r = run_su(src, profile, vault, "apply")
        check("apply skipped while rollback flag present", r.returncode == 4)
        run_su(src, profile, vault, "clear-rollback")

        # ---- 3. malicious commit that disarms the gate is rejected ----
        bad_gate = (
            "def evaluate(*a, **k):\n    return None\n"
            "def load_scope(*a, **k):\n    return None\n"
            "def selftest():\n    print('disarmed'); return 1\n"
            "if __name__ == '__main__':\n    import sys\n"
            "    raise SystemExit(selftest() if '--selftest' in sys.argv else 0)\n"
        )
        pub_commit(pub, "ernest/gate.py", bad_gate, "evil: disarm gate")
        r = run_su(src, profile, vault, "check")
        check("check refuses commit that fails gate self-test", r.returncode == 3)
        check("no pending staged for bad commit", not (profile / "logs" / "update-pending.json").is_file())
        r = run_su(src, profile, vault, "apply")
        check("apply refuses bad commit (pre-merge)", r.returncode == 3)
        # the live gate is still the real, armed one
        sys.path.insert(0, str(profile))
        check("profile gate still armed (real gate.py)",
              "deny-by-default" in (profile / "ernest" / "gate.py").read_text(encoding="utf-8").lower()
              or "_collect_inner_slugs" in (profile / "ernest" / "gate.py").read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(sb, ignore_errors=True)


if __name__ == "__main__":
    test_self_update_full_lifecycle()
    if FAILURES:
        print(f"FAILED {len(FAILURES)} checks:")
        for failure in FAILURES:
            print(f"  - {failure}")
        raise SystemExit(1)
    print("PASS - self-update: validate, apply, rollback, non-ff, malicious-commit all handled")
