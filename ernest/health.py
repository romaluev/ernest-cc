"""Four-state health audit + safe-class self-repair (the self-healing loop).

Doctor v2. Every check reports one of four states (taxonomy borrowed from the
last30days skill's `doctor`, see docs/research/self-improving-systems.md):

    WORKING     verified good right now
    UNVERIFIED  configured/plausible but not proven (e.g. MCP present, unprobed)
    BROKEN      verified bad — something the CEO relies on will misbehave
    OFF         intentionally absent (valid state, e.g. local-exports-only mode)

Each check carries evidence, a one-line remedy, and an `auto_fixable` flag.
`heal()` applies ONLY the auto-fixable class (regenerate/restore config that the
engine itself owns), and every fix is: snapshot -> apply -> re-run the failed
check -> keep or revert. Escalation follows the production self-healing ladder
(auto-fix -> health card in the daily flow -> /ernest-doctor session); nothing
here ever touches credentials, sends, or files outside `scope.write`.

Last-good snapshots: whenever a config file parses clean during an audit, a copy
lands in `logs/snapshots/`. That is what `heal` restores from — customization is
preserved; code defaults are only the fallback of last resort.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import concerns, connect
from .config import Config

WORKING, UNVERIFIED, BROKEN, OFF = "WORKING", "UNVERIFIED", "BROKEN", "OFF"

# Don't re-attempt the same auto-fix within this window if it failed (fix-storm
# brake, from the patrol-loop pattern).
_COOLDOWN_SECONDS = 3600


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


@dataclass
class Check:
    id: str            # stable id, e.g. "concerns.parse"
    subsystem: str     # engine | memory | concerns | grading | vault | connectors | data | schedule | gate
    state: str         # WORKING | UNVERIFIED | BROKEN | OFF
    evidence: str      # what was observed
    remedy: str        # one line: how a human (or heal) fixes it
    auto_fixable: bool = False

    def as_dict(self) -> Dict[str, object]:
        return {"id": self.id, "subsystem": self.subsystem, "state": self.state,
                "evidence": self.evidence, "remedy": self.remedy,
                "auto_fixable": self.auto_fixable}


def snapshots_dir(cfg: Config) -> Path:
    return cfg.logs_dir / "snapshots"


def repairs_log(cfg: Config) -> Path:
    return cfg.logs_dir / "repairs.jsonl"


def repairs_dir(cfg: Config) -> Path:
    return cfg.logs_dir / "repairs"


def _snapshot_if_valid(cfg: Config, src: Path) -> None:
    """Refresh the last-good copy of a config file that just passed its check."""
    try:
        dst = snapshots_dir(cfg) / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.is_file() or dst.read_bytes() != src.read_bytes():
            shutil.copy2(src, dst)
    except OSError:
        pass  # snapshotting is best-effort; never break the audit itself


def _log_repair(cfg: Config, entry: Dict[str, object]) -> None:
    try:
        repairs_log(cfg).parent.mkdir(parents=True, exist_ok=True)
        with repairs_log(cfg).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _recent_failed_fix(cfg: Config, check_id: str) -> bool:
    """True if this check's auto-fix failed within the cooldown window."""
    path = repairs_log(cfg)
    if not path.is_file():
        return False
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()[-50:]
    except OSError:
        return False
    now = datetime.now(timezone.utc)
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("check") != check_id or entry.get("verified") is not False:
            continue
        try:
            at = datetime.strptime(str(entry.get("at", "")), "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
        return (now - at.replace(tzinfo=timezone.utc)).total_seconds() < _COOLDOWN_SECONDS
    return False


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #

def _check_engine_imports(cfg: Config) -> List[Check]:
    broken: List[str] = []
    for mod in ("ernest.watch", "ernest.grading", "ernest.read_threads",
                "ernest.audit", "ernest.brief", "ernest.render"):
        try:
            __import__(mod)
        except Exception as exc:  # noqa: BLE001 — any import breakage counts
            broken.append(f"{mod} ({exc})")
    if broken:
        return [Check("engine.imports", "engine", BROKEN, "; ".join(broken),
                      "Run `./install.sh --refresh` or `/ernest-doctor` to repair the install.")]
    return [Check("engine.imports", "engine", WORKING, "all core modules import", "—")]


def _check_memory(cfg: Config) -> List[Check]:
    out: List[Check] = []
    core = [n for n in ("company-core.md", "ceo-persona.md")
            if not (cfg.memory_dir / n).is_file()]
    if core:
        out.append(Check("memory.core", "memory", BROKEN,
                         f"missing: {', '.join(core)}",
                         "Restore from repo or re-run `/ernest-onboard` — these hold who you are."))
    else:
        out.append(Check("memory.core", "memory", WORKING, "company-core + ceo-persona present", "—"))
    icp = [n for n in ("icp-b2b.md", "icp-talent.md") if not (cfg.memory_dir / n).is_file()]
    if icp:
        out.append(Check("memory.icp", "memory", UNVERIFIED,
                         f"missing: {', '.join(icp)}",
                         "Restore from repo or `./install.sh --refresh`; grading falls back to JSON/defaults."))
    else:
        out.append(Check("memory.icp", "memory", WORKING, "ICP memos present", "—"))
    prefs = cfg.memory_dir / "preferences.md"
    if prefs.is_file():
        out.append(Check("memory.preferences", "memory", WORKING, "preferences.md present", "—"))
    else:
        out.append(Check("memory.preferences", "memory", BROKEN,
                         "memory/preferences.md missing — engine settings fall back to defaults silently",
                         "Auto-fixable: `ernest heal` writes the default engine-settings file.",
                         auto_fixable=True))
    return out


def _check_concerns(cfg: Config) -> List[Check]:
    cst = concerns.status(cfg)
    if cst.level == "error":
        return [Check("concerns.parse", "concerns", BROKEN,
                      f"{cst.message} — ALL watch reminders are silently OFF",
                      "Auto-fixable: `ernest heal` restores the last-good standing-concerns.md.",
                      auto_fixable=True)]
    if not cfg.concerns_file.is_file():
        return [Check("concerns.parse", "concerns", BROKEN,
                      "memory/standing-concerns.md missing — no watch reminders",
                      "Auto-fixable: `ernest heal` restores the last-good copy (or re-onboard).",
                      auto_fixable=True)]
    enabled = [c.id for c in concerns.load(cfg) if c.enabled]
    if not enabled:
        return [Check("concerns.enabled", "concerns", OFF,
                      "concerns file parses but nothing is enabled",
                      "Enable one with `ernest enable-concern <id>` or add via `ernest new-automation`.")]
    # Snapshot ONLY a proven-good file (parses + has enabled concerns) — a
    # zero-concern file must never become the restore source.
    _snapshot_if_valid(cfg, cfg.concerns_file)
    return [Check("concerns.parse", "concerns", WORKING,
                  f"{len(enabled)} enabled: {', '.join(enabled[:6])}", "—")]


def _check_grading(cfg: Config) -> List[Check]:
    from . import grading  # local import to keep import-breakage visible in engine.imports
    out: List[Check] = []
    for kind in ("b2b", "talent"):
        path = cfg.data_dir / "grading" / f"{kind}-rubric.json"
        cid = f"grading.{kind}"
        if not path.is_file():
            out.append(Check(cid, "grading", BROKEN,
                             f"data/grading/{kind}-rubric.json missing — engine silently falls back to built-in defaults (your customizations are gone)",
                             "Auto-fixable: `ernest heal` restores the last-good copy (else code defaults).",
                             auto_fixable=True))
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            out.append(Check(cid, "grading", BROKEN,
                             f"{path.name} does not parse ({exc}) — grading falls back to defaults",
                             "Auto-fixable: `ernest heal` restores the last-good copy (else code defaults).",
                             auto_fixable=True))
            continue
        # The wholesale-replace footgun: the JSON REPLACES code defaults — a
        # missing top-level key silently disables that whole signal family.
        missing = [k for k in grading._DEFAULTS.get(kind, {}) if k not in data]
        if missing:
            out.append(Check(cid, "grading", UNVERIFIED,
                             f"{path.name} lacks key(s) {missing} — those signals are OFF (JSON replaces defaults, no merge)",
                             f"Add the missing key(s) back to {path.name} (copy from ernest/grading.py _DEFAULTS), then re-run `ernest grade`."))
        else:
            _snapshot_if_valid(cfg, path)
            out.append(Check(cid, "grading", WORKING, f"{path.name} valid, all signal families present", "—"))
    return out


def _check_vault(cfg: Config) -> List[Check]:
    # Missing dirs on a fresh profile are normal (every command creates them);
    # creating them here mirrors engine behavior. BROKEN only when creation or
    # writing actually fails.
    try:
        from .config import ensure_dirs
        ensure_dirs(cfg)
    except OSError as exc:
        return [Check("vault.dirs", "vault", BROKEN,
                      f"cannot create vault/log dirs ({exc})",
                      "Fix permissions on the vault path, or point ERNEST_LOCAL_VAULT elsewhere.")]
    probe = cfg.logs_dir / ".write-probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return [Check("vault.writable", "vault", BROKEN, f"logs dir not writable ({exc})",
                      "Fix permissions on the profile directory.")]
    return [Check("vault.dirs", "vault", WORKING, "vault + logs dirs present and writable", "—")]


def _check_connectors(cfg: Config) -> List[Check]:
    out: List[Check] = []
    if cfg.mode == "vps":
        url = connect.resolve_url(cfg)
        if not url:
            out.append(Check("connectors.brain", "connectors", BROKEN,
                             "vps mode but no brain URL persisted",
                             "Run `/ernest-connect-brain` again, or `/ernest-go-local`."))
        else:
            ok, detail = connect.health_probe(url)
            out.append(Check("connectors.brain", "connectors",
                             WORKING if ok else BROKEN,
                             f"{url} ({detail})",
                             "—" if ok else "Brain offline: check the VPS / token, or `/ernest-go-local` meanwhile."))
        return out
    servers: List[str] = []
    if cfg.mcp_file.is_file():
        try:
            servers = sorted(json.loads(cfg.mcp_file.read_text(encoding="utf-8"))
                             .get("mcpServers", {}).keys())
        except (OSError, ValueError):
            out.append(Check("connectors.mcp", "connectors", BROKEN,
                             ".mcp.json exists but does not parse",
                             "Re-run the installer or `/ernest-connect-brain` to rewrite it."))
            return out
    if servers:
        out.append(Check("connectors.mcp", "connectors", UNVERIFIED,
                         f"configured (not probed): {', '.join(servers)}",
                         "Use each connector once in Claude to verify auth still works."))
    else:
        out.append(Check("connectors.mcp", "connectors", OFF,
                         "no MCP connectors — running on data/ exports (valid local mode)",
                         "To go live, add a connector (docs/connectors.md) or `/ernest-connect-brain`."))
    return out


def _check_data(cfg: Config) -> List[Check]:
    mail = cfg.data_dir / "mail"
    if mail.is_dir() and any(mail.iterdir()):
        return [Check("data.mail", "data", WORKING, "mail exports present", "—")]
    return [Check("data.mail", "data", UNVERIFIED,
                  "data/mail is empty — watch/grade have nothing to read locally",
                  "Drop exports in data/mail/ (see data/README.md) or connect a mail MCP.")]


def _check_gate(cfg: Config) -> List[Check]:
    try:
        import contextlib
        import io
        from . import gate
        with contextlib.redirect_stdout(io.StringIO()):  # selftest prints; keep audits clean
            rc = gate.selftest()
    except Exception as exc:  # noqa: BLE001
        return [Check("gate.selftest", "gate", BROKEN, f"selftest crashed: {exc}",
                      "The draft-first guardrail is compromised — reinstall before trusting sends are blocked.")]
    if rc == 0:
        return [Check("gate.selftest", "gate", WORKING, "draft-first guardrail selftest passes", "—")]
    return [Check("gate.selftest", "gate", BROKEN, f"selftest failed (rc={rc})",
                  "Reinstall (`./install.sh --refresh`) — do NOT rely on the send-block until this passes.")]


def _check_onboarded(cfg: Config) -> List[Check]:
    if (cfg.vault_dir / ".onboarded").is_file():
        return [Check("profile.onboarded", "engine", WORKING, "personalized (onboarded)", "—")]
    return [Check("profile.onboarded", "engine", OFF,
                  "running on SAMPLE data (not onboarded yet)",
                  "Run `/ernest-setup` (or `ernest onboard`) to make it yours.")]


def run_checks(cfg: Config) -> List[Check]:
    """The full audit. Deterministic, read-only except last-good snapshots."""
    checks: List[Check] = []
    for fn in (_check_engine_imports, _check_memory, _check_concerns, _check_grading,
               _check_vault, _check_connectors, _check_data, _check_gate, _check_onboarded):
        try:
            checks.extend(fn(cfg))
        except Exception as exc:  # noqa: BLE001 — a crashing check IS a finding
            checks.append(Check(f"audit.{fn.__name__}", "engine", BROKEN,
                                f"health check itself crashed: {exc}",
                                "Report this; run `/ernest-doctor`."))
    return checks


def summary(checks: List[Check]) -> Dict[str, int]:
    out = {WORKING: 0, UNVERIFIED: 0, BROKEN: 0, OFF: 0}
    for c in checks:
        out[c.state] = out.get(c.state, 0) + 1
    return out


def to_json(checks: List[Check]) -> str:
    return json.dumps({"at": _now(), "summary": summary(checks),
                       "checks": [c.as_dict() for c in checks]},
                      ensure_ascii=False, indent=1)


# --------------------------------------------------------------------------- #
# Auto-repair (safe class only)
# --------------------------------------------------------------------------- #

def _fix_preferences(cfg: Config) -> bool:
    from . import preferences
    path = cfg.memory_dir / "preferences.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"{k}: {v}" for k, v in preferences.DEFAULTS.items())
    path.write_text(
        "# Preferences (regenerated defaults)\n\n"
        "Ernest recreated this file after finding it missing. Tune freely.\n\n"
        "## Engine settings\n\n" + lines + "\n\n## Learned (Ernest appends below)\n",
        encoding="utf-8")
    return True


def _restore_from_snapshot(cfg: Config, target: Path, defaults_writer: Optional[Callable[[], str]] = None) -> bool:
    snap = snapshots_dir(cfg) / target.name
    target.parent.mkdir(parents=True, exist_ok=True)
    if snap.is_file():
        shutil.copy2(snap, target)
        return True
    if defaults_writer is not None:
        target.write_text(defaults_writer(), encoding="utf-8")
        return True
    return False


def _fix_concerns(cfg: Config) -> bool:
    return _restore_from_snapshot(cfg, cfg.concerns_file)


def _grading_defaults_writer(kind: str) -> Callable[[], str]:
    def _write() -> str:
        from . import grading
        return json.dumps(grading._DEFAULTS.get(kind, {}), ensure_ascii=False, indent=2) + "\n"
    return _write


_FIXERS: Dict[str, Callable[[Config], bool]] = {
    "memory.preferences": _fix_preferences,
    "concerns.parse": _fix_concerns,
    "grading.b2b": lambda cfg: _restore_from_snapshot(
        cfg, cfg.data_dir / "grading" / "b2b-rubric.json", _grading_defaults_writer("b2b")),
    "grading.talent": lambda cfg: _restore_from_snapshot(
        cfg, cfg.data_dir / "grading" / "talent-rubric.json", _grading_defaults_writer("talent")),
}

_RECHECKS: Dict[str, Callable[[Config], List[Check]]] = {
    "memory.preferences": _check_memory,
    "concerns.parse": _check_concerns,
    "grading.b2b": _check_grading,
    "grading.talent": _check_grading,
}


def _backup_broken(cfg: Config, check_id: str) -> Optional[str]:
    """Preserve the broken artifact as evidence before touching it."""
    targets = {
        "concerns.parse": cfg.concerns_file,
        "grading.b2b": cfg.data_dir / "grading" / "b2b-rubric.json",
        "grading.talent": cfg.data_dir / "grading" / "talent-rubric.json",
    }
    src = targets.get(check_id)
    if src is None or not src.is_file():
        return None
    try:
        dst = repairs_dir(cfg) / f"{src.name}@{_stamp()}.broken"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return str(dst)
    except OSError:
        return None


def heal(cfg: Config, checks: Optional[List[Check]] = None) -> List[Dict[str, object]]:
    """Apply the auto-fixable class: snapshot -> fix -> re-check -> keep/report.

    Returns one repair record per attempted fix (also appended to repairs.jsonl).
    Never touches credentials, connectors, or anything outside scope.write.
    """
    checks = checks if checks is not None else run_checks(cfg)
    repairs: List[Dict[str, object]] = []
    for check in checks:
        if check.state != BROKEN or not check.auto_fixable:
            continue
        fixer = _FIXERS.get(check.id)
        if fixer is None:
            continue
        if _recent_failed_fix(cfg, check.id):
            repairs.append({"at": _now(), "check": check.id, "action": "skipped",
                            "verified": False, "note": "cooldown: same fix failed <1h ago"})
            continue
        backup = _backup_broken(cfg, check.id)
        try:
            applied = fixer(cfg)
        except Exception as exc:  # noqa: BLE001
            applied = False
            check.evidence += f" (fix crashed: {exc})"
        verified = False
        if applied:
            recheck = _RECHECKS.get(check.id)
            if recheck is not None:
                after = {c.id: c for c in recheck(cfg)}
                verified = after.get(check.id) is None or after[check.id].state != BROKEN
        entry: Dict[str, object] = {"at": _now(), "check": check.id,
                                    "action": "auto-fix" if applied else "fix-unavailable",
                                    "verified": verified}
        if backup:
            entry["broken_backup"] = backup
        _log_repair(cfg, entry)
        repairs.append(entry)
    return repairs


def record_failure(cfg: Config, command: str, exc: BaseException) -> None:
    """Crash capture: the engine never breaks silently (called from cli.main)."""
    try:
        _log_repair(cfg, {"at": _now(), "check": f"crash.{command}", "action": "captured",
                          "verified": False, "error": f"{type(exc).__name__}: {exc}"})
        write_health_card(cfg, [Check(f"crash.{command}", "engine", BROKEN,
                                      f"`ernest {command}` crashed: {type(exc).__name__}: {exc}",
                                      "Run `ernest doctor` then `/ernest-doctor` for guided repair.")])
    except Exception:  # noqa: BLE001 — failure capture must never raise
        pass


# --------------------------------------------------------------------------- #
# Health card (escalation surface — lands in the daily flow)
# --------------------------------------------------------------------------- #

def write_health_card(cfg: Config, checks: List[Check]) -> Optional[Path]:
    """Write 00-Watch/ernest-health--{date}.md for BROKEN findings (canonical
    card format, so breakage shows up exactly where the CEO already looks).
    Returns None when nothing is broken — silence means healthy."""
    broken = [c for c in checks if c.state == BROKEN]
    if not broken:
        return None
    from .config import _today  # same date source as the rest of the engine
    stamp = _today().isoformat()
    cfg.watch_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Watch: ernest-health ({stamp})", "",
        "type: reminder-card",
        "source: engine-health",
        f"items: {len(broken)}", "",
        "Remind only. Auto-fixable items: run `ernest heal`. Everything else: `/ernest-doctor`.", "",
    ]
    for i, c in enumerate(broken, 1):
        lines += [f"## {i}. [BROKEN] {c.id}",
                  f"- why: {c.evidence}",
                  f"- action: {c.remedy}",
                  f"- context: subsystem={c.subsystem}, auto_fixable={'yes' if c.auto_fixable else 'no'}",
                  ""]
    lines.append("Reply draft these when you want me to prepare actions.")
    path = cfg.watch_dir / f"ernest-health--{stamp}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
