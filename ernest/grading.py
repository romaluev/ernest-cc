"""Deterministic tier grading for B2B leads and talent.

This is the "working system" behind the ICP rubrics in `memory/icp-b2b.md` and
`memory/icp-talent.md`. It produces an explainable tier with reasons, a
confidence level, and flags for the judgment calls a rule engine cannot make
(e.g. "is this actually Fortune 500?", "are they likely interested?").

Signal priority, matching the memory rubrics:
  1. CRM tier (passed in) — trusted first.
  2. Curated lists in `data/grading/*.json`.
  3. Inference from text — lowest confidence; always flagged.

The Claude layer (skills `b2b-lead-grading`, `talent-sourcing-grading`) reads the
full thread/profile, uses this grade as a starting signal, and resolves flags
with public knowledge or CRM lookups.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .config import Config

# Tier ordering for sorting (lower number = higher priority).
B2B_RANK = {"tier-1": 0, "tier-2": 1, "trash": 2, "unknown": 3}
TALENT_RANK = {"tier-1": 0, "tier-2": 1, "tier-3": 2, "unknown": 3}


@dataclass
class Grade:
    tier: str
    confidence: str  # high | medium | low
    reasons: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)

    @property
    def rank(self) -> int:
        return B2B_RANK.get(self.tier, TALENT_RANK.get(self.tier, 3))


def pool_name(cfg: Optional[Config]) -> str:
    """Current talent outreach pool — a changeable snapshot, not hardcoded."""
    return _load_rubric(cfg, "talent").get("pool", "talent") or "talent"


def _load_rubric(cfg: Optional[Config], kind: str) -> dict:
    if cfg is not None:
        path = cfg.data_dir / "grading" / f"{kind}-rubric.json"
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
    return _DEFAULTS.get(kind, {})


def _hay(*parts: str) -> str:
    return " " + " ".join(p.lower() for p in parts if p) + " "


def _any_in(text: str, needles: List[str]) -> Optional[str]:
    for n in needles:
        if n and n.lower() in text:
            return n
    return None


# --------------------------------------------------------------------------- #
# B2B grading
# --------------------------------------------------------------------------- #

def grade_b2b(
    *,
    company: str = "",
    contact: str = "",
    text: str = "",
    category: str = "",
    crm_tier: str = "",
    prior_contact: bool = False,
    fund_aum_busd: Optional[float] = None,
    cfg: Optional[Config] = None,
    rubric: Optional[dict] = None,
) -> Grade:
    r = rubric if rubric is not None else _load_rubric(cfg, "b2b")
    t1 = r.get("tier1", {})
    trash = r.get("trash", {})
    hay = _hay(company, contact, text, category)
    reasons: List[str] = []
    flags: List[str] = []

    # 1. CRM tier wins.
    crm_map = {k.lower(): v for k, v in r.get("crm_tier_map", {}).items()}
    if crm_tier and crm_tier.lower() in crm_map:
        tier = crm_map[crm_tier.lower()]
        return Grade(tier, "high", [f"CRM tier '{crm_tier}' -> {tier}"], [])

    # 2. Tier-1 list/intent signals.
    hit = _any_in(hay, t1.get("categories", []))
    if hit:
        reasons.append(f"ICP category match: {hit}")
    prov = _any_in(hay, t1.get("providers", []))
    if prov:
        reasons.append(f"Model/cloud provider: {prov}")
    comp = _any_in(hay, t1.get("companies", []))
    if comp:
        reasons.append(f"Major company on list: {comp}")
    person = _any_in(hay, t1.get("people", []))
    if person:
        reasons.append(f"High-reputation person: {person}")
    intent = _any_in(hay, t1.get("intent_keywords", []))
    if intent:
        reasons.append(f"Enterprise buying intent: '{intent}'")
    rep = _any_in(hay, t1.get("reputation_keywords", []))
    if rep or prior_contact:
        reasons.append("Prior contact with Alex" if prior_contact else f"Mentions Alex: '{rep}'")
    threshold = float(t1.get("fund_aum_threshold_busd", 2.0))
    if fund_aum_busd is not None and fund_aum_busd > threshold:
        reasons.append(f"Large fund: ~${fund_aum_busd}B AUM (> ${threshold}B)")

    if reasons:
        # List/category hits are high confidence; pure intent-keyword is medium.
        strong = bool(hit or prov or comp or person or rep or prior_contact
                      or (fund_aum_busd is not None and fund_aum_busd > threshold))
        return Grade("tier-1", "high" if strong else "medium", reasons, flags)

    # 3. Trash signals.
    vendor = _any_in(hay, trash.get("vendor_keywords", []))
    small_media = _any_in(hay, trash.get("small_media_keywords", []))
    if vendor:
        return Grade("trash", "medium",
                     [f"Cold vendor pitch: '{vendor}', no Tier-1 signal"], flags)
    if small_media:
        flags.append("Confirm audience size (< ~100k readers = trash, else Tier-2 media).")
        return Grade("trash", "low", [f"Small-media signal: '{small_media}'"], flags)

    # 4. Default: Tier-2, low confidence — needs a human/LLM check.
    flags.append("No Tier-1 list/intent hit and not obvious trash. Verify "
                 "Fortune 500 / Forbes 2000 / market-leader status before upgrading.")
    return Grade("tier-2", "low",
                 ["No decisive signal; defaulting to Tier-2"], flags)


# --------------------------------------------------------------------------- #
# Talent grading
# --------------------------------------------------------------------------- #

def grade_talent(
    *,
    name: str = "",
    profile: str = "",
    company: str = "",
    title: str = "",
    cfg: Optional[Config] = None,
    rubric: Optional[dict] = None,
) -> Grade:
    r = rubric if rubric is not None else _load_rubric(cfg, "talent")
    t1 = r.get("tier1", {})
    t2 = r.get("tier2", {})
    excl = r.get("exclusions", {})
    hay = _hay(name, profile, company, title)
    reasons: List[str] = []
    flags: List[str] = []

    # Hard filter: current Northwind employee/investor -> not a target.
    cur = _any_in(hay, excl.get("current_company", []))
    inv = _any_in(hay, excl.get("investor_terms", []))
    if cur:
        return Grade("tier-3", "high",
                     [f"Excluded: appears to be current Northwind ('{cur}')"], [])
    if inv:
        return Grade("tier-3", "high",
                     [f"Excluded: appears to be a Northwind investor ('{inv}')"], [])

    # Tier-1 signals. A Tier-1 country alone is NOT a qualifier; it only
    # strengthens "strong B2B/B2C experience in a Tier-1 country".
    big_tech = _any_in(hay, t1.get("big_tech", []))
    senior = _any_in(hay, t1.get("senior_titles", []))
    country = _any_in(hay, t1.get("tier1_countries", []))
    ai_media = _any_in(hay, t1.get("ai_media_models", []))
    strong_tech = _any_in(hay, t1.get("strong_tech_keywords", []))
    commercial = _any_in(hay, t1.get("commercial_keywords", []))

    structural = False
    if big_tech and senior:
        reasons.append(f"Senior role ('{senior}') at Big Tech ('{big_tech}')")
        structural = True
    if strong_tech:
        reasons.append(f"Strong technical base: '{strong_tech}'")
        structural = True
    if ai_media:
        reasons.append(f"Strong in AI media products/models: '{ai_media}'")
        structural = True
    if commercial and country:
        reasons.append(f"Strong B2B/B2C experience ('{commercial}') in Tier-1 country ('{country.strip()}')")

    if reasons:
        confidence = "high" if structural else "medium"
        flags.append("Confirm they're likely interested in Northwind (judgment call).")
        return Grade("tier-1", confidence, reasons, flags)

    # Tier-2 signals.
    t2_reasons: List[str] = []
    if big_tech:
        t2_reasons.append(f"Big Tech experience: '{big_tech}'")
    us_startup = _any_in(hay, t2.get("us_startup_signals", []))
    if us_startup:
        t2_reasons.append(f"US startup signal: '{us_startup}'")
    gtm = _any_in(hay, t2.get("product_gtm_keywords", []))
    if gtm:
        t2_reasons.append(f"Product/GTM experience: '{gtm}'")
    if ai_media:
        t2_reasons.append(f"Worked with AI media models: '{ai_media}'")

    if t2_reasons:
        flags.append("Confirm interest + that they're not a current Northwind investor/employee.")
        return Grade("tier-2", "low", t2_reasons, flags)

    flags.append("No Tier-1/2 signal found in profile text. Read the full profile "
                 "before discarding — local text may be thin.")
    return Grade("tier-3", "low", ["No qualifying signal in available text"], flags)


_DEFAULTS: Dict[str, dict] = {
    "b2b": {
        "crm_tier_map": {"vip": "tier-1", "investor": "tier-1", "partner": "tier-2"},
        "tier1": {
            "categories": ["ai studio", "ad agency", "creative agency", "model provider", "cloud provider", "enterprise"],
            "providers": ["openai", "anthropic", "aws", "azure", "google cloud", "nvidia"],
            "companies": ["google", "microsoft", "amazon", "meta", "nvidia", "coca-cola", "nike"],
            "people": ["harry stebbings", "ilya sutskever"],
            "intent_keywords": ["enterprise", "procurement", "rollout", "contract", "seats", "rfp"],
            "reputation_keywords": ["spoke with alex", "talked with alex", "met alex", "as discussed with alex", "alex suggested", "sam rivera"],
            "fund_aum_threshold_busd": 2.0,
        },
        "trash": {
            "vendor_keywords": ["we offer", "guest post", "backlink", "seo services", "link building"],
            "small_media_reader_threshold": 100000,
            "small_media_keywords": ["newsletter", "blog", "small publication"],
        },
    },
    "talent": {
        "pool": "ex-NovaLabs",
        "tier1": {
            "big_tech": ["google", "meta", "apple", "amazon", "microsoft", "nvidia", "openai", "anthropic", "snap", "tiktok", "bytedance", "stripe"],
            "senior_titles": ["team lead", "lead", "head of", "director", "vp", "principal", "staff", "chief", "founder", "co-founder"],
            "tier1_countries": ["united states", "usa", "uk", "united kingdom", "canada", "germany", "france", "singapore", "israel"],
            "ai_media_models": ["stable diffusion", "sora", "runway", "midjourney", "flux", "diffusion", "text-to-video", "generative video"],
            "strong_tech_keywords": ["machine learning", "deep learning", "computer vision", "phd", "icpc"],
            "commercial_keywords": ["b2b", "b2c", "enterprise sales", "head of sales", "vp sales", "scaled revenue", "grew revenue", "commercial lead"],
        },
        "tier2": {
            "us_startup_signals": ["y combinator", "yc", "series a", "series b", "san francisco", "bay area", "startup"],
            "product_gtm_keywords": ["product manager", "go-to-market", "gtm", "growth", "partnerships", "business development"],
        },
        "exclusions": {
            "current_company": ["northwind"],
            "investor_terms": ["northwind investor", "invested in northwind"],
        },
    },
}
