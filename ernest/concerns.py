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
