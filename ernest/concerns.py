"""Standing-concerns parsing and registration.

`memory/standing-concerns.md` holds a fenced YAML block the CEO edits by talking
to Ernest, never by hand. We parse that block with a tiny purpose-built reader
(no third-party YAML) and append new concerns in place.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from .config import Config

_FENCE_RE = re.compile(r"```ya?ml\s*\n(.*?)```", re.DOTALL)


@dataclass
class Concern:
    id: str
    playbook: str
    enabled: bool = True
    params: Dict[str, str] = field(default_factory=dict)


def _yaml_block(text: str) -> str:
    match = _FENCE_RE.search(text)
    return match.group(1) if match else ""


def parse(text: str) -> List[Concern]:
    block = _yaml_block(text)
    concerns: List[Concern] = []
    current: Concern | None = None
    in_params = False
    for raw in block.splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        stripped = raw.strip()
        if stripped.startswith("- id:"):
            if current is not None:
                concerns.append(current)
            current = Concern(id=stripped.split(":", 1)[1].strip(), playbook="")
            in_params = False
            continue
        if current is None:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if key == "playbook":
            current.playbook = value
        elif key == "enabled":
            current.enabled = value.lower() in ("true", "yes", "1")
        elif key == "params":
            in_params = True
        elif in_params and indent >= 6 and value != "":
            current.params[key] = value.strip().strip('"')
    if current is not None:
        concerns.append(current)
    return concerns


def load(cfg: Config) -> List[Concern]:
    if not cfg.concerns_file.is_file():
        return []
    return parse(cfg.concerns_file.read_text(encoding="utf-8"))


@dataclass
class ConcernsStatus:
    count: int          # number of ENABLED concerns that will actually run
    level: str          # "ok" | "warn" | "error"
    message: str


def status(cfg: Config) -> ConcernsStatus:
    """Distinguish 'legitimately no concerns' from 'config is broken so reminders
    are silently OFF'. The second case must be LOUD — otherwise the product goes
    dark while doctor says 'ok' and the brief says 'inbox clean'.
    """
    path = cfg.concerns_file
    if not path.is_file():
        return ConcernsStatus(0, "warn",
            "standing-concerns.md not found — no watch reminders are active. Run setup/onboarding.")
    text = path.read_text(encoding="utf-8")
    concerns = parse(text)
    has_fence = _FENCE_RE.search(text) is not None
    if concerns:
        enabled = sum(1 for c in concerns if c.enabled)
        if enabled == 0:
            return ConcernsStatus(0, "error",
                f"{len(concerns)} concern(s) defined but ALL are disabled — NO reminders will run.")
        return ConcernsStatus(enabled, "ok", f"{enabled} active watch concern(s).")
    # Zero concerns parsed — is the file broken, or genuinely empty?
    if not has_fence:
        if "- id:" in text or "playbook" in text or len(text.strip()) > 200:
            return ConcernsStatus(0, "error",
                "standing-concerns.md has content but its ```yaml block is missing/mis-typed — "
                "ALL watch reminders are OFF. Fix the YAML fence (```yaml ... ```).")
        return ConcernsStatus(0, "warn", "No watch concerns defined yet.")
    if _yaml_block(text).strip():
        return ConcernsStatus(0, "error",
            "standing-concerns.md has a ```yaml block but no concerns could be parsed — "
            "it is malformed, so ALL watch reminders are OFF.")
    return ConcernsStatus(0, "warn", "standing-concerns.md ```yaml block is empty — no concerns defined.")


def set_enabled(cfg: Config, concern_id: str, enabled: bool) -> bool:
    """Flip a concern on/off in place — the simple rollback for an adopted automation.
    Returns False if the concern id isn't found."""
    if not cfg.concerns_file.is_file():
        return False
    text = cfg.concerns_file.read_text(encoding="utf-8")
    lines = text.splitlines()
    in_target = False
    found = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("- id:"):
            in_target = stripped.split(":", 1)[1].strip() == concern_id
        elif in_target and stripped.startswith("enabled:"):
            indent = line[:len(line) - len(line.lstrip())]
            lines[i] = f"{indent}enabled: {'true' if enabled else 'false'}"
            found = True
            in_target = False
    if found:
        cfg.concerns_file.write_text("\n".join(lines) + ("\n" if text.endswith("\n") else ""),
                                     encoding="utf-8")
    return found


def register(cfg: Config, concern: Concern) -> bool:
    """Append a concern into the YAML block. Returns False if id already exists."""
    text = cfg.concerns_file.read_text(encoding="utf-8")
    if any(c.id == concern.id for c in parse(text)):
        return False
    match = _FENCE_RE.search(text)
    if not match:
        raise ValueError("standing-concerns.md is missing its YAML block")

    param_lines = "".join(f'      {k}: "{v}"\n' for k, v in concern.params.items())
    entry = (
        f"\n  - id: {concern.id}\n"
        f"    playbook: {concern.playbook}\n"
        f"    enabled: {'true' if concern.enabled else 'false'}\n"
        f"    params:\n{param_lines}"
    )
    block = match.group(1).rstrip("\n")
    new_block = f"{block}\n{entry}"
    updated = text[:match.start(1)] + new_block + "\n" + text[match.end(1):]
    cfg.concerns_file.write_text(updated, encoding="utf-8")
    return True
