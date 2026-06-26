"""Onboarding: seed memory from the CEO's answers and drop a marker.

Non-interactive mode (used by installers and tests) takes flags. Interactive
mode prompts for the few essentials. Either way it only writes to `memory/`
and the vault marker - never to connectors.

MEMORY-SAFE: re-running onboarding never destroys existing memory. Before writing
it backs up memory/ and then MERGES — existing non-empty values and any custom
bullets the CEO (or Ernest) added are preserved; onboarding only fills blanks.

LOCAL-FIRST: defaults assume everything stays on this machine (no CRM, no remote
brain) unless the CEO says otherwise. This matches the confidentiality/NDA posture.
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .config import Config


@dataclass
class Answers:
    name: str = ""
    role: str = "CEO"
    company: str = ""
    icp: str = ""
    redlines: str = ""


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        value = ""
    return value or default


def gather_interactive() -> Answers:
    print("Ernest onboarding - a few essentials (Enter to accept defaults).\n")
    return Answers(
        name=_ask("Your name"),
        role=_ask("Your role", "CEO"),
        company=_ask("Company name"),
        icp=_ask("Ideal customer (ICP)"),
        redlines=_ask("Hard red lines Ernest must never cross"),
    )


_FIELD_RE = re.compile(r"-\s*([^:]+):\s*(.*)")


def _field_map(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for line in text.splitlines():
        m = _FIELD_RE.match(line.strip())
        if m:
            out[m.group(1).strip()] = m.group(2).strip()
    return out


def _merge_lines(old_text: str, new_lines: List[str]) -> List[str]:
    """Preserve existing non-empty field values + custom bullets; fill only blanks."""
    old = _field_map(old_text)
    merged: List[str] = []
    seen: set[str] = set()
    for line in new_lines:
        m = _FIELD_RE.match(line.strip())
        if m:
            key = m.group(1).strip()
            seen.add(key)
            existing = old.get(key, "")
            if existing:  # never clobber a value the CEO already has
                merged.append(f"- {key}: {existing}")
                continue
        merged.append(line)
    for key, val in old.items():  # keep CEO/Ernest-added bullets not in the template
        if key not in seen and val:
            merged.append(f"- {key}: {val}")
    return merged


def _backup_memory(cfg: Config) -> Optional[Path]:
    files = [p for p in cfg.memory_dir.glob("*.md")] if cfg.memory_dir.is_dir() else []
    if not files:
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = cfg.memory_dir / ".backups" / stamp
    dest.mkdir(parents=True, exist_ok=True)
    for p in files:
        shutil.copy2(p, dest / p.name)
    return dest


def _write_merged(path: Path, new_lines: List[str]) -> None:
    if path.is_file():
        new_lines = _merge_lines(path.read_text(encoding="utf-8"), new_lines)
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _company_core_lines(a: Answers) -> List[str]:
    return [
        "# Company Core",
        "",
        "Filled during onboarding from the CEO's answers. Local-first by default.",
        "",
        f"- Company: {a.company}",
        f"- ICP: {a.icp}",
        "- Verticals / offers:",
        f"- Red lines (never do): {a.redlines}",
        "- CRM: none yet (tell Ernest which CRM you use — HubSpot, Salesforce, or none)",
        "- Email / calendar: none yet (connect Gmail or Microsoft 365 when you want live data)",
        "- Comms posture: draft-first; CEO approves every send",
        "- Memory: stays on this machine (local-only) unless you choose a server",
        "- Remote brain: none (local-only)",
    ]


def _persona_lines(a: Answers) -> List[str]:
    return [
        "# CEO Persona",
        "",
        f"- Name: {a.name or '(set during onboarding)'}",
        f"- Role: {a.role or 'CEO'}",
        f"- Company: {a.company or '(set during onboarding)'}",
        "- Relationship tiers: clients / investors / partners / candidates / press / team",
        "- Voice fingerprint: concise, direct, warm-professional; short greeting and"
        " sign-off. Auto-refined from the CEO's real sent mail once a mail connector"
        " is authorized; until then drafts stay neutral and must be reviewed.",
        f"- Yes / no rules: {a.redlines or 'Never send, post, or commit externally without explicit approval.'}",
        "- Authority ceiling: L2 (drafts and proposals). L3 (money/legal/credentials) is manual only.",
        "- Approval preferences: review drafts in batches; approve sends individually.",
        "- Current season / priorities: set in memory/north-star.md and standing-concerns.md.",
    ]


def run(cfg: Config, answers: Optional[Answers]) -> Answers:
    cfg.memory_dir.mkdir(parents=True, exist_ok=True)
    a = answers if answers is not None else gather_interactive()
    # Never destroy existing memory: back up first, then merge-fill blanks only.
    _backup_memory(cfg)
    _write_merged(cfg.memory_dir / "company-core.md", _company_core_lines(a))
    _write_merged(cfg.memory_dir / "ceo-persona.md", _persona_lines(a))
    cfg.vault_dir.mkdir(parents=True, exist_ok=True)
    (cfg.vault_dir / ".onboarded").write_text(
        f"onboarded: {cfg.today.isoformat()}\ncompany: {a.company}\n", encoding="utf-8"
    )
    return a
