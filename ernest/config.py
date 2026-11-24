"""Runtime configuration for the Ernest engine.

All paths resolve from the active profile directory so the engine behaves
identically in the repo, in an installed `~/.ernest-cc` profile, or in a test
sandbox. Nothing here touches the network.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


def _today() -> date:
    override = os.environ.get("ERNEST_TODAY", "").strip()
    if override:
        return datetime.strptime(override, "%Y-%m-%d").date()
    return date.today()


@dataclass(frozen=True)
class Config:
    profile_dir: Path
    vault_dir: Path
    memory_dir: Path
    data_dir: Path
    logs_dir: Path
    skills_dir: Path
    mode: str
    today: date

    @property
    def watch_dir(self) -> Path:
        return self.vault_dir / "Ernest" / "00-Watch"

    @property
    def daily_dir(self) -> Path:
        return self.vault_dir / "Ernest" / "00-Daily"

    @property
    def drafts_dir(self) -> Path:
        return self.vault_dir / "Ernest" / "00-Drafts"

    @property
    def concerns_file(self) -> Path:
        return self.memory_dir / "standing-concerns.md"

    @property
    def mcp_file(self) -> Path:
        return self.profile_dir / ".mcp.json"

    @property
    def connection_file(self) -> Path:
        """Durable surface↔brain wiring (mode + brain URL, never a secret).

        Lets `/ernest-connect-brain` switch a surface to VPS-brain mode without a
        terminal env var, and survive across sessions. `ERNEST_MODE` still wins
        when explicitly set."""
        return self.profile_dir / "connection.json"


def read_connection(profile: Path) -> dict:
    """Read persisted connection state ({mode, brain_url}); empty if none/bad."""
    path = profile / "connection.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def load() -> Config:
    profile = Path(os.environ.get("ERNEST_PROFILE_DIR", os.getcwd())).resolve()
    vault_env = os.environ.get("ERNEST_LOCAL_VAULT", "").strip()
    vault = Path(vault_env).resolve() if vault_env else profile / "vault"
    # Mode precedence: explicit env > persisted connection.json > local default.
    mode = os.environ.get("ERNEST_MODE", "").strip().lower()
    if not mode:
        mode = str(read_connection(profile).get("mode", "")).strip().lower()
    # Allowlist: a corrupted/hand-edited mode must degrade to local, not pass through.
    if mode not in ("local", "vps"):
        mode = "local"
    return Config(
        profile_dir=profile,
        vault_dir=vault,
        memory_dir=profile / "memory",
        data_dir=profile / "data",
        logs_dir=profile / "logs",
        skills_dir=profile / "skills",
        mode=mode,
        today=_today(),
    )


def ensure_dirs(cfg: Config) -> None:
    for path in (cfg.watch_dir, cfg.daily_dir, cfg.drafts_dir, cfg.logs_dir,
                 cfg.vault_dir / "Ernest" / "00-Threads"):
        path.mkdir(parents=True, exist_ok=True)
