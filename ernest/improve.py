"""Typed, evidence-ranked improvement proposals with versioned apply/rollback.

The self-improving loop's brain. Mines four signal streams —

    logs/learning-proposals.jsonl   typed correction candidates (Stop hook)
    logs/feedback.jsonl             explicit `ernest feedback` notes
    logs/repairs.jsonl              self-healing events (recurring breakage)
    logs/usage.jsonl                telemetry (dead concerns, measurement)

— and turns them into proposals that carry their EVIDENCE (how many independent
signals support them; ready at >= 3, the recurrence bar every studied system
uses), a concrete machine-applicable DIFF, and its REVERSE diff. Nothing is
ever applied without an explicit `ernest learn --apply <key>` (L2 — the CEO's
action). Every apply: snapshot -> change -> sandbox selftest -> keep or revert,
logged to logs/applied.jsonl; `--rollback <id>` restores any prior apply. If
post-apply signals get WORSE, the next report auto-proposes the rollback
(the backtrack pattern — see docs/research/self-improving-systems.md).
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import concerns, telemetry
from .config import Config

READY_THRESHOLD = 3      # signals needed before a proposal is marked ready
STALE_DAYS = 30          # concern silent this long (with runs) -> propose disable
STALE_MIN_RUNS = 5
REGRESSION_SIGNALS = 2   # post-apply complaints that trigger a rollback proposal

_TIER_FIX_RE = re.compile(
    r"(?i)\b(?P<subj>[\w&.'-]+(?:\s+[\w&.'-]+){0,3}?)\s+(?:was|is|it'?s)\s+actually\s+"
    r"(?P<tier>tier[- ]?[123]|trash)\b")
_STOPWORDS = {"the", "that", "this", "it", "he", "she", "they", "thread", "lead",
              "one", "and", "but", "a", "an", "you", "we", "i", "again", "graded",
              "grade", "marked", "said", "no", "wrong", "actually"}
_TIER_TOKEN_RE = re.compile(r"(?i)^(tier-?\d|trash)$")
_DAYS_RE = re.compile(r"^(\d+)d$")
_MAX_POINTS_RE = re.compile(r"(?i)max (\d+) (?:points|bullets|items|key points)")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def versions_dir(cfg: Config) -> Path:
    return cfg.logs_dir / "versions"


def applied_log(cfg: Config) -> Path:
    return cfg.logs_dir / "applied.jsonl"


def _read_jsonl(path: Path) -> List[Dict[str, object]]:
    if not path.is_file():
        return []
    out: List[Dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _signals(cfg: Config) -> List[Dict[str, object]]:
    """All correction-class signals, normalized to {at, signal_type, text}."""
    from . import learn
    out: List[Dict[str, object]] = []
    for e in _read_jsonl(cfg.logs_dir / "learning-proposals.jsonl"):
        stype = str(e.get("signal_type") or "new_use_case")
        out.append({"at": str(e.get("captured_at", "")), "signal_type": stype,
                    "text": str(e.get("observed_pattern", ""))})
    for e in _read_jsonl(cfg.logs_dir / "feedback.jsonl"):
        note = str(e.get("note", ""))
        stype = learn.classify(note)
        if stype:
            out.append({"at": str(e.get("at", "")), "signal_type": stype, "text": note})
    return out


def _clean_subject(raw: str) -> str:
    words = [w for w in raw.strip().split()
             if w.lower() not in _STOPWORDS and not _TIER_TOKEN_RE.match(w)]
    return " ".join(words).strip(" .,:;\"'")


def _slug(text: str) -> str:
    return "-".join(re.findall(r"[a-z0-9]+", text.lower()))[:48] or "x"


# --------------------------------------------------------------------------- #
# Proposal generation
# --------------------------------------------------------------------------- #

def _bump_days(value: str, delta: int = 3) -> Optional[str]:
    match = _DAYS_RE.match(value.strip().strip('"'))
    if not match:
        return None
    return f"{int(match.group(1)) + delta}d"


def generate(cfg: Config) -> List[Dict[str, object]]:
    signals = _signals(cfg)
    enabled = {c.id: c for c in concerns.load(cfg) if c.enabled}
    proposals: List[Dict[str, object]] = []

    # 1. rubric_add — "X was actually tier-1/trash" corrections, grouped by subject.
    groups: Dict[Tuple[str, str], List[Dict[str, object]]] = {}
    for s in signals:
        if s["signal_type"] != "rubric_correction":
            continue
        m = _TIER_FIX_RE.search(str(s["text"]))
        if not m:
            continue
        subj = _clean_subject(m.group("subj"))
        tier = m.group("tier").lower().replace(" ", "-").replace("tier-", "tier-")
        if subj:
            groups.setdefault((subj.lower(), tier), []).append(s)
    for (subj, tier), evid in sorted(groups.items()):
        target = cfg.data_dir / "grading" / "b2b-rubric.json"
        if tier == "tier-1":
            diff = {"file": str(target), "op": "list_add",
                    "path": ["tier1", "companies"], "value": subj}
        elif tier == "trash":
            diff = {"file": str(target), "op": "list_add",
                    "path": ["trash", "vendor_keywords"], "value": subj}
        else:
            diff = None  # tier-2/3 corrections need judgment, not a list edit
        proposals.append({
            "key": f"rubric-{_slug(subj)}-{tier}",
            "kind": "rubric_add",
            "title": f"Grade '{subj}' as {tier} (CEO corrected the tier {len(evid)}x)",
            "evidence": [f"{e['at']}: {str(e['text'])[:110]}" for e in evid],
            "evidence_count": len(evid),
            "ready": len(evid) >= READY_THRESHOLD,
            "target": str(target),
            "diff": diff,
            "reverse": ({"file": str(target), "op": "list_remove",
                         "path": diff["path"], "value": subj} if diff else None),
            "note": (None if diff else
                     "tier-2/3 corrections are judgment calls — update memory/icp-b2b.md "
                     "or the CRM tier instead of a signal list."),
        })

    # 2. threshold_tune — noise complaints attributed to a concern.
    noise: Dict[str, List[Dict[str, object]]] = {}
    for s in signals:
        if s["signal_type"] != "threshold_complaint":
            continue
        text = str(s["text"]).lower()
        matched = next((cid for cid in enabled if cid.lower() in text), None)
        if matched is None and ("follow" in text or "followup" in text):
            matched = next((cid for cid in enabled if "followup" in cid), None)
        if matched:
            noise.setdefault(matched, []).append(s)
    for cid, evid in sorted(noise.items()):
        current = enabled[cid].params.get("staleness", "7d").strip('"')
        bumped = _bump_days(current)
        proposals.append({
            "key": f"tune-{_slug(cid)}-staleness",
            "kind": "threshold_tune",
            "title": f"'{cid}' is too noisy ({len(evid)} complaint(s)) — raise staleness {current} -> {bumped or '?'}",
            "evidence": [f"{e['at']}: {str(e['text'])[:110]}" for e in evid],
            "evidence_count": len(evid),
            "ready": len(evid) >= READY_THRESHOLD,
            "target": str(cfg.concerns_file),
            "diff": ({"op": "concern_param", "concern": cid, "param": "staleness",
                      "from": current, "to": bumped} if bumped else None),
            "reverse": ({"op": "concern_param", "concern": cid, "param": "staleness",
                         "from": bumped, "to": current} if bumped else None),
        })

    # 3. disable_stale — a concern that has fired nothing for 30d of runs.
    stats = telemetry.concern_stats(cfg)
    for cid, s in sorted(stats.items()):
        if cid not in enabled or int(s.get("runs", 0)) < STALE_MIN_RUNS:
            continue
        quiet_days = telemetry.days_since(cfg, str(s.get("last_fired") or s.get("first_seen")))
        if int(s.get("items_total", 0)) == 0 and quiet_days is not None and quiet_days >= STALE_DAYS:
            proposals.append({
                "key": f"disable-{_slug(cid)}",
                "kind": "disable_stale",
                "title": f"'{cid}' fired 0 items in {int(s['runs'])} runs over {quiet_days}d — disable it?",
                "evidence": [f"telemetry: runs={s['runs']}, items_total=0, quiet={quiet_days}d"],
                "evidence_count": int(s["runs"]),
                "ready": True,
                "target": str(cfg.concerns_file),
                "diff": {"op": "concern_enabled", "concern": cid, "to": False},
                "reverse": {"op": "concern_enabled", "concern": cid, "to": True},
            })

    # 4. preference — parsable taste corrections -> engine-settings change.
    from . import preferences
    prefs = preferences.load(cfg)
    pref_groups: Dict[Tuple[str, str], List[Dict[str, object]]] = {}
    for s in signals:
        if s["signal_type"] != "preference":
            continue
        text = str(s["text"]).lower()
        change: Optional[Tuple[str, str]] = None
        if "prefer pdf" in text:
            change = ("read_more_format", "pdf")
        elif "prefer html" in text:
            change = ("read_more_format", "html")
        elif (m := _MAX_POINTS_RE.search(text)):
            change = ("max_key_points", m.group(1))
        elif "too long" in text or "too verbose" in text or "too detailed" in text:
            change = ("max_key_points", str(max(3, int(prefs.get("max_key_points", "6")) - 2)))
        if change:
            pref_groups.setdefault(change, []).append(s)
    for (key, value), evid in sorted(pref_groups.items()):
        current = prefs.get(key, "")
        if str(current) == value:
            continue
        proposals.append({
            "key": f"pref-{_slug(key)}-{_slug(value)}",
            "kind": "preference",
            "title": f"Set {key}: {current} -> {value} ({len(evid)} signal(s))",
            "evidence": [f"{e['at']}: {str(e['text'])[:110]}" for e in evid],
            "evidence_count": len(evid),
            "ready": len(evid) >= 1,  # preferences are L1 — one clear signal is enough
            "target": str(cfg.memory_dir / "preferences.md"),
            "diff": {"op": "pref_set", "key": key, "from": str(current), "to": value},
            "reverse": {"op": "pref_set", "key": key, "from": value, "to": str(current)},
        })

    # 5. rollback (backtrack) — an applied change whose post-apply signals got worse.
    applied = [e for e in _read_jsonl(applied_log(cfg))
               if e.get("action") == "apply" and not e.get("rolled_back")]
    for entry in applied:
        applied_at = str(entry.get("at", ""))
        concern = str((entry.get("diff") or {}).get("concern", ""))
        after = [s for s in signals
                 if str(s["at"]) > applied_at
                 and s["signal_type"] in ("threshold_complaint", "rubric_correction", "missed_item")
                 and (not concern or concern.lower() in str(s["text"]).lower())]
        if len(after) >= REGRESSION_SIGNALS:
            proposals.append({
                "key": f"rollback-{entry.get('id')}",
                "kind": "rollback",
                "title": f"Applied change {entry.get('id')} ({entry.get('key')}) made things worse "
                         f"({len(after)} new complaint(s) since) — roll it back?",
                "evidence": [f"{s['at']}: {str(s['text'])[:110]}" for s in after[:4]],
                "evidence_count": len(after),
                "ready": True,
                "target": str(entry.get("target", "")),
                "diff": {"op": "rollback", "applied_id": str(entry.get("id"))},
                "reverse": None,
            })

    # 6. make_stick — the same breakage healed 3+ times deserves a durable fix.
    repair_counts: Dict[str, int] = {}
    for e in _read_jsonl(cfg.logs_dir / "repairs.jsonl"):
        cid = str(e.get("check", ""))
        if cid:
            repair_counts[cid] = repair_counts.get(cid, 0) + 1
    for cid, n in sorted(repair_counts.items()):
        if n >= READY_THRESHOLD:
            proposals.append({
                "key": f"stick-{_slug(cid)}",
                "kind": "make_stick",
                "title": f"'{cid}' broke/healed {n}x — find the root cause, not another repair",
                "evidence": [f"logs/repairs.jsonl: {n} entries for {cid}"],
                "evidence_count": n,
                "ready": True,
                "target": "judgment (see ernest-self-repair step 6)",
                "diff": None, "reverse": None,
            })

    proposals.sort(key=lambda p: (not p["ready"], -int(p["evidence_count"])))
    return proposals


# --------------------------------------------------------------------------- #
# Apply / rollback (versioned, selftest-gated)
# --------------------------------------------------------------------------- #

def _snapshot(cfg: Config, target: Path) -> Optional[str]:
    if not target.is_file():
        return None
    dst = versions_dir(cfg) / f"{target.name}@{_stamp()}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, dst)
    return str(dst)


def _rewrite_concern_param(cfg: Config, concern_id: str, param: str, value: str) -> bool:
    text = cfg.concerns_file.read_text(encoding="utf-8")
    lines = text.splitlines()
    in_target = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("- id:"):
            in_target = stripped.split(":", 1)[1].strip() == concern_id
        elif in_target and stripped.startswith(f"{param}:"):
            indent = line[:len(line) - len(line.lstrip())]
            quoted = f'"{value}"' if '"' in stripped else value
            lines[i] = f"{indent}{param}: {quoted}"
            cfg.concerns_file.write_text("\n".join(lines) + ("\n" if text.endswith("\n") else ""),
                                         encoding="utf-8")
            return True
    return False


def _set_pref(cfg: Config, key: str, value: str) -> bool:
    """Edit the `- key: value` bullet inside the Engine settings block, matching
    exactly what ernest/preferences.py::load parses."""
    path = cfg.memory_dir / "preferences.md"
    if not path.is_file():
        return False
    lines = path.read_text(encoding="utf-8").splitlines()
    in_settings = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## "):
            if in_settings:  # left the settings block without finding the key
                lines.insert(i, f"- {key}: {value}")
                break
            in_settings = "engine settings" in stripped.lower()
            continue
        if in_settings and stripped.startswith("- ") and \
                stripped[2:].partition(":")[0].strip() == key:
            indent = line[:len(line) - len(line.lstrip())]
            lines[i] = f"{indent}- {key}: {value}"
            break
    else:
        if in_settings:
            lines.append(f"- {key}: {value}")
        else:
            lines += ["", "## Engine settings", "", f"- {key}: {value}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def _apply_diff(cfg: Config, diff: Dict[str, object]) -> bool:
    op = diff.get("op")
    if op in ("list_add", "list_remove"):
        target = Path(str(diff["file"]))
        data = json.loads(target.read_text(encoding="utf-8"))
        node = data
        path = list(diff["path"])  # type: ignore[arg-type]
        for part in path[:-1]:
            node = node.setdefault(part, {})
        lst = node.setdefault(path[-1], [])
        value = str(diff["value"])
        if op == "list_add" and value not in lst:
            lst.append(value)
        elif op == "list_remove" and value in lst:
            lst.remove(value)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return True
    if op == "concern_param":
        return _rewrite_concern_param(cfg, str(diff["concern"]), str(diff["param"]), str(diff["to"]))
    if op == "concern_enabled":
        return concerns.set_enabled(cfg, str(diff["concern"]), bool(diff["to"]))
    if op == "pref_set":
        return _set_pref(cfg, str(diff["key"]), str(diff["to"]))
    return False


def _log_applied(cfg: Config, entry: Dict[str, object]) -> None:
    applied_log(cfg).parent.mkdir(parents=True, exist_ok=True)
    with applied_log(cfg).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def apply(cfg: Config, key: str, run_selftest: bool = True) -> Dict[str, object]:
    """Apply one proposal by key: snapshot -> diff -> selftest -> keep/revert.
    This IS the approval step — it only ever runs because the CEO invoked it."""
    proposal = next((p for p in generate(cfg) if p["key"] == key), None)
    if proposal is None:
        raise ValueError(f"No proposal with key '{key}'. Run `ernest learn` to list them.")
    diff = proposal.get("diff")
    if diff is None:
        raise ValueError(f"Proposal '{key}' is a judgment call — it has no machine diff. "
                         f"{proposal.get('note') or proposal.get('target')}")
    if diff.get("op") == "rollback":
        return rollback(cfg, str(diff["applied_id"]))

    target = Path(str(proposal["target"]))
    snapshot = _snapshot(cfg, target)
    if not _apply_diff(cfg, diff):  # type: ignore[arg-type]
        raise ValueError(f"Could not apply '{key}' — target line/file not found ({target}).")

    entry: Dict[str, object] = {
        "id": f"A{_stamp()}", "at": _now(), "action": "apply", "key": key,
        "kind": proposal["kind"], "target": str(target), "diff": diff,
        "reverse": proposal.get("reverse"), "snapshot": snapshot,
        "evidence_count": proposal["evidence_count"],
    }
    if run_selftest:
        from . import selftest as selftest_mod
        ok, report = selftest_mod.run(cfg)
        entry["selftest"] = "pass" if ok else "fail"
        if not ok:
            if snapshot:
                shutil.copy2(snapshot, target)
            entry["action"] = "reverted"
            entry["note"] = "selftest failed after apply — change reverted"
            _log_applied(cfg, entry)
            return {"applied": False, "entry": entry, "selftest_report": report}
    _log_applied(cfg, entry)
    return {"applied": True, "entry": entry}


def rollback(cfg: Config, applied_id: str) -> Dict[str, object]:
    entries = _read_jsonl(applied_log(cfg))
    entry = next((e for e in entries
                  if str(e.get("id")) == applied_id and e.get("action") == "apply"), None)
    if entry is None:
        raise ValueError(f"No applied change '{applied_id}'. See `ernest learn` (Applied changes).")
    reverse = entry.get("reverse")
    snapshot = entry.get("snapshot")
    restored = False
    if snapshot and Path(str(snapshot)).is_file():
        shutil.copy2(str(snapshot), str(entry["target"]))
        restored = True
    elif isinstance(reverse, dict):
        restored = _apply_diff(cfg, reverse)
    if not restored:
        raise ValueError(f"Cannot roll back '{applied_id}': no snapshot and no reverse diff.")
    _log_applied(cfg, {"id": f"R{_stamp()}", "at": _now(), "action": "rollback",
                       "rollback_of": applied_id, "target": entry.get("target"),
                       "via": "snapshot" if snapshot else "reverse-diff"})
    # Mark the original entry (append-only log: rewrite is avoided; readers treat
    # a rollback entry as the marker).
    return {"rolled_back": applied_id, "via": "snapshot" if snapshot else "reverse-diff"}


# --------------------------------------------------------------------------- #
# Report (appended to learning-summary.md by `ernest learn`)
# --------------------------------------------------------------------------- #

def report_lines(cfg: Config) -> List[str]:
    proposals = generate(cfg)
    rolled = {str(e.get("rollback_of")) for e in _read_jsonl(applied_log(cfg))
              if e.get("action") == "rollback"}
    applied = [e for e in _read_jsonl(applied_log(cfg)) if e.get("action") == "apply"]
    lines: List[str] = ["", "---", "", "## Typed proposals (evidence-ranked)", ""]
    typed = [p for p in proposals]
    if not typed:
        lines.append("- No typed proposals yet. Signals accumulate from corrections "
                     "(`ernest feedback`), sessions, repairs, and telemetry.")
    for p in typed:
        marker = "READY" if p["ready"] else f"collecting ({p['evidence_count']}/{READY_THRESHOLD})"
        lines.append(f"### [{marker}] {p['title']}")
        for ev in list(p["evidence"])[:3]:
            lines.append(f"- evidence: {ev}")
        if p.get("diff"):
            lines.append(f"- diff: `{json.dumps(p['diff'], ensure_ascii=False)}`")
            lines.append(f"- apply: `ernest learn --apply {p['key']}`  (L2 — your call; "
                         f"reversible via rollback)")
        else:
            lines.append(f"- action: {p.get('note') or p.get('target')}")
        lines.append("")
    lines += ["## Applied changes & measurement", ""]
    if not applied:
        lines.append("- Nothing applied yet.")
    for e in applied:
        status = "ROLLED BACK" if str(e.get("id")) in rolled else \
                 ("reverted (selftest failed)" if e.get("action") == "reverted" else "active")
        lines.append(f"- {e.get('id')} [{status}] {e.get('key')} — target {e.get('target')}; "
                     f"selftest {e.get('selftest', '-')}; rollback: "
                     f"`ernest learn --rollback {e.get('id')}`")
    lines.append("")
    return lines


def append_report(cfg: Config, summary_path: Path) -> None:
    with summary_path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(report_lines(cfg)))
