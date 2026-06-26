"""Runtime configuration for the Ernest engine.

All paths resolve from the active profile directory so the engine behaves
identically in the repo, in an installed `~/.ernest-cc` profile, or in a test
sandbox. Nothing here touches the network.
"""
from __future__ import annotations

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


def load() -> Config:
    profile = Path(os.environ.get("ERNEST_PROFILE_DIR", os.getcwd())).resolve()
    vault_env = os.environ.get("ERNEST_LOCAL_VAULT", "").strip()
    vault = Path(vault_env).resolve() if vault_env else profile / "vault"
    return Config(
        profile_dir=profile,
        vault_dir=vault,
        memory_dir=profile / "memory",
        data_dir=profile / "data",
        logs_dir=profile / "logs",
        skills_dir=profile / "skills",
        mode=os.environ.get("ERNEST_MODE", "local").strip().lower() or "local",
        today=_today(),
    )


def ensure_dirs(cfg: Config) -> None:
    for path in (cfg.watch_dir, cfg.daily_dir, cfg.drafts_dir, cfg.logs_dir,
                 cfg.vault_dir / "Ernest" / "00-Threads"):
        path.mkdir(parents=True, exist_ok=True)
