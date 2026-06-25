"""Onboarding: seed memory from the CEO's answers and drop a marker.

Non-interactive mode (used by installers and tests) takes flags. Interactive
mode prompts for the few essentials. Either way it only writes to `memory/`
and the vault marker - never to connectors.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

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


def _write_company_core(cfg: Config, a: Answers) -> None:
    path = cfg.memory_dir / "company-core.md"
    path.write_text("\n".join([
        "# Company Core",
        "",
        "Filled during onboarding from the CEO's answers and connected data.",
        "",
        f"- Company: {a.company}",
        f"- ICP: {a.icp}",
        "- Verticals / offers:",
        f"- Red lines (never do): {a.redlines}",
        "- CRM: HubSpot (canonical)",
        "- Email / calendar: Gmail or Microsoft 365, whichever is connected",
        "- Comms posture: draft-first; CEO approves send",
        "- Remote brain: VPS Ernest when configured",
        "- Local fallback: enabled",
        "",
    ]), encoding="utf-8")


def _write_persona(cfg: Config, a: Answers) -> None:
    path = cfg.memory_dir / "ceo-persona.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    header = f"# CEO Persona\n\n- Name: {a.name}\n- Role: {a.role}\n"
    if text.lstrip().startswith("# CEO Persona"):
        body = text.split("\n", 1)[1] if "\n" in text else ""
        path.write_text(header + body, encoding="utf-8")
    else:
        path.write_text(header + "\n" + text, encoding="utf-8")


def run(cfg: Config, answers: Optional[Answers]) -> Answers:
    cfg.memory_dir.mkdir(parents=True, exist_ok=True)
    a = answers if answers is not None else gather_interactive()
    _write_company_core(cfg, a)
    _write_persona(cfg, a)
    cfg.vault_dir.mkdir(parents=True, exist_ok=True)
    (cfg.vault_dir / ".onboarded").write_text(
        f"onboarded: {cfg.today.isoformat()}\ncompany: {a.company}\n", encoding="utf-8"
    )
    return a
