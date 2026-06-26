"""Deterministic tier grading for B2B leads and talent.

This is the "working system" behind the ICP rubrics in `memory/icp-b2b.md` and
`memory/icp-talent.md`. It produces an explainable tier with reasons, a
confidence level, a numeric SCORE (for ranking within a tier), and flags for the
judgment calls a rule engine cannot make.

Why a score: a tier alone can't sort. Two Tier-1 leads are not equal — one may
hit five strong signals, another just one. The score counts ALL matched signals
(weighted, with density), so the strongest candidates rise to the top instead of
being ordered only by date. The Claude layer reads the full thread/profile, uses
this as a starting signal, and resolves flags with public knowledge or CRM/ATS
lookups — and should cast a WIDE net first, then let this rank it.

Signal priority, matching the memory rubrics:
  1. CRM/ATS tier (passed in) — trusted first.
  2. Curated lists in `data/grading/*.json` (broaden these freely).
  3. Inference from text — lowest confidence; always flagged.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .config import Config

# Tier ordering for sorting (lower number = higher priority).
B2B_RANK = {"tier-1": 0, "tier-2": 1, "trash": 2, "unknown": 3}
TALENT_RANK = {"tier-1": 0, "tier-2": 1, "tier-3": 2, "unknown": 3}

# Common abbreviations / variants, expanded in the haystack so matching isn't
# brittle ("Sr." == senior, "ML" == machine learning, "SWE" == software engineer).
_ABBREV = {
    r"\bsr\.?\b": "senior",
    r"\bjr\.?\b": "junior",
    r"\bswe\b": "software engineer",
    r"\beng\b": "engineer",
    r"\bml\b": "machine learning",
    r"\bdl\b": "deep learning",
    r"\bcv\b": "computer vision",
    r"\bnlp\b": "natural language processing",
    r"\bgen ?ai\b": "generative ai",
    r"\bllm\b": "large language model",
    r"\bvp\b": "vice president",
    r"\bgtm\b": "go-to-market",
    r"\bbd\b": "business development",
    r"\bpm\b": "product manager",
    r"\bt2v\b": "text-to-video",
    r"\bt2i\b": "text-to-image",
}


@dataclass
class Grade:
    tier: str
    confidence: str  # high | medium | low
    reasons: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    score: float = 0.0  # higher = stronger match; used to rank within a tier

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
    text = " " + " ".join(p.lower() for p in parts if p) + " "
    text = re.sub(r"[‐-―]", "-", text)  # normalize fancy dashes
    for pat, repl in _ABBREV.items():
        text = re.sub(pat, repl, text)
    return text


def _any_in(text: str, needles: List[str]) -> Optional[str]:
    for n in needles:
        if n and n.lower() in text:
            return n
    return None


def _all_in(text: str, needles: List[str]) -> List[str]:
    """Every distinct needle present — for signal density / scoring."""
    seen: List[str] = []
    for n in needles:
        if n and n.lower() in text and n not in seen:
            seen.append(n)
    return seen


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
    score = 0.0

    # 1. CRM tier wins.
    crm_map = {k.lower(): v for k, v in r.get("crm_tier_map", {}).items()}
    if crm_tier and crm_tier.lower() in crm_map:
        tier = crm_map[crm_tier.lower()]
        base = 100.0 if tier == "tier-1" else 60.0
        return Grade(tier, "high", [f"CRM tier '{crm_tier}' -> {tier}"], [], base)

    # 2. Tier-1 list/intent signals — count ALL hits for density/score.
    cats = _all_in(hay, t1.get("categories", []))
    provs = _all_in(hay, t1.get("providers", []))
    comps = _all_in(hay, t1.get("companies", []))
    people = _all_in(hay, t1.get("people", []))
    intents = _all_in(hay, t1.get("intent_keywords", []))
    reps = _all_in(hay, t1.get("reputation_keywords", []))
    if cats:
        reasons.append(f"ICP category: {', '.join(cats[:3])}"); score += 8 * len(cats)
    if provs:
        reasons.append(f"Model/cloud provider: {', '.join(provs[:3])}"); score += 12 * len(provs)
    if comps:
        reasons.append(f"Major company: {', '.join(comps[:3])}"); score += 12 * len(comps)
    if people:
        reasons.append(f"High-reputation person: {', '.join(people[:3])}"); score += 15 * len(people)
    if intents:
        reasons.append(f"Enterprise buying intent: {', '.join(intents[:3])}"); score += 6 * len(intents)
    if reps or prior_contact:
        reasons.append("Prior contact (CRM)" if prior_contact else f"References the CEO: {', '.join(reps[:2])}")
        score += 14
    threshold = float(t1.get("fund_aum_threshold_busd", 2.0))
    if fund_aum_busd is not None and fund_aum_busd > threshold:
        reasons.append(f"Large fund: ~${fund_aum_busd}B AUM (> ${threshold}B)"); score += 15

    if reasons:
        strong = bool(cats or provs or comps or people or reps or prior_contact
                      or (fund_aum_busd is not None and fund_aum_busd > threshold))
        return Grade("tier-1", "high" if strong else "medium", reasons, flags, score)

    # 3. Trash signals.
    vendor = _any_in(hay, trash.get("vendor_keywords", []))
    small_media = _any_in(hay, trash.get("small_media_keywords", []))
    if vendor:
        return Grade("trash", "medium", [f"Cold vendor pitch: '{vendor}', no Tier-1 signal"], flags, 0.0)
    if small_media:
        flags.append("Confirm audience size (< ~100k readers = trash, else Tier-2 media).")
        return Grade("trash", "low", [f"Small-media signal: '{small_media}'"], flags, 0.0)

    # 4. Default: Tier-2, low confidence — needs a human/LLM check.
    flags.append("No Tier-1 list/intent hit and not obvious trash. Verify "
                 "market-leader / enterprise status before upgrading.")
    return Grade("tier-2", "low", ["No decisive signal; defaulting to Tier-2"], flags, 2.0)


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
    score = 0.0
    pool = r.get("pool", "this") or "this"

    # Hard filter: current employee/investor of OUR company -> not a target.
    cur = _any_in(hay, excl.get("current_company", []))
    inv = _any_in(hay, excl.get("investor_terms", []))
    if cur:
        return Grade("tier-3", "high", [f"Excluded: appears to be a current employee ('{cur}')"], [], 0.0)
    if inv:
        return Grade("tier-3", "high", [f"Excluded: appears to be an investor ('{inv}')"], [], 0.0)

    big_tech = _all_in(hay, t1.get("big_tech", []))
    senior = _any_in(hay, t1.get("senior_titles", []))
    country = _any_in(hay, t1.get("tier1_countries", []))
    ai_media = _all_in(hay, t1.get("ai_media_models", []))
    strong_tech = _all_in(hay, t1.get("strong_tech_keywords", []))
    commercial = _any_in(hay, t1.get("commercial_keywords", []))

    structural = False
    if big_tech and senior:
        reasons.append(f"Senior role ('{senior}') at {', '.join(big_tech[:2])}"); score += 16; structural = True
    if strong_tech:
        reasons.append(f"Strong technical base: {', '.join(strong_tech[:3])}"); score += 12 * len(strong_tech); structural = True
    if ai_media:
        reasons.append(f"AI media products/models: {', '.join(ai_media[:3])}"); score += 12 * len(ai_media); structural = True
    if commercial and country:
        reasons.append(f"Commercial strength ('{commercial}') in Tier-1 country ('{country.strip()}')"); score += 14

    if reasons:
        confidence = "high" if structural else "medium"
        flags.append(f"Confirm they're likely interested in {pool} (judgment call).")
        return Grade("tier-1", confidence, reasons, flags, score)

    # Tier-2 signals — a single relevant signal is enough to surface as an option.
    t2_reasons: List[str] = []
    if big_tech:
        t2_reasons.append(f"Big Tech experience: {', '.join(big_tech[:2])}"); score += 8 * len(big_tech)
    us_startup = _any_in(hay, t2.get("us_startup_signals", []))
    if us_startup:
        t2_reasons.append(f"US startup signal: '{us_startup}'"); score += 5
    gtm = _any_in(hay, t2.get("product_gtm_keywords", []))
    if gtm:
        t2_reasons.append(f"Product/GTM experience: '{gtm}'"); score += 5
    if ai_media:
        t2_reasons.append(f"Worked with AI media models: {', '.join(ai_media[:2])}")
    if country:
        score += 2

    if t2_reasons:
        # A single relevant signal -> tier-2 (an option to consider), not tier-3.
        flags.append(f"Confirm interest + that they're not a current {pool} investor/employee.")
        return Grade("tier-2", "low", t2_reasons, flags, score)

    flags.append("No Tier-1/2 signal found in profile text. Read the full profile "
                 "before discarding — local text may be thin.")
    return Grade("tier-3", "low", ["No qualifying signal in available text"], flags, 0.0)


_DEFAULTS: Dict[str, dict] = {
    "b2b": {
        "crm_tier_map": {"vip": "tier-1", "investor": "tier-1", "partner": "tier-2"},
        "tier1": {
            "categories": ["ai studio", "ad agency", "creative agency", "media agency",
                           "marketing agency", "model provider", "cloud provider", "enterprise"],
            "providers": ["openai", "anthropic", "deepmind", "mistral", "cohere", "aws",
                          "azure", "google cloud", "gcp", "nvidia", "coreweave"],
            "companies": ["google", "microsoft", "amazon", "apple", "meta", "nvidia", "netflix",
                          "coca-cola", "pepsico", "nike", "adidas", "unilever", "disney",
                          "samsung", "publicis", "wpp", "omnicom", "accenture", "deloitte"],
            "people": ["harry stebbings", "ilya sutskever"],
            "intent_keywords": ["enterprise", "procurement", "rollout", "contract", "msa",
                                "seats", "rfp", "rfi", "purchase order", "annual plan", "pilot for"],
            "reputation_keywords": ["spoke with alex", "talked with alex", "met alex",
                                    "as discussed with alex", "alex suggested", "sam rivera"],
            "fund_aum_threshold_busd": 2.0,
        },
        "trash": {
            "vendor_keywords": ["we offer", "guest post", "backlink", "seo services",
                                "link building", "lead generation service", "press release distribution"],
            "small_media_reader_threshold": 100000,
            "small_media_keywords": ["newsletter", "blog", "small publication"],
        },
    },
    "talent": {
        "pool": "ex-NovaLabs",
        "tier1": {
            "big_tech": ["google", "alphabet", "deepmind", "meta", "facebook", "instagram",
                         "apple", "amazon", "microsoft", "nvidia", "openai", "anthropic",
                         "netflix", "uber", "airbnb", "snap", "tiktok", "bytedance", "stripe",
                         "tesla", "linkedin", "databricks", "scale ai", "figma", "adobe",
                         "salesforce", "spotify", "pinterest", "roblox", "unity", "midjourney",
                         "runway", "pika", "hugging face", "character.ai", "perplexity", "cohere"],
            "senior_titles": ["senior", "team lead", "tech lead", "engineering lead",
                              "lead engineer", "head of", "director", "vice president",
                              "principal", "staff", "chief", "cto", "cpo", "founder",
                              "co-founder", "engineering manager", "architect"],
            "tier1_countries": ["united states", "usa", " us ", "u.s.", "uk", "united kingdom",
                                "canada", "germany", "france", "singapore", "switzerland",
                                "netherlands", "sweden", "australia", "israel", "ireland", "japan"],
            "ai_media_models": ["stable diffusion", "sdxl", "sora", "runway", "midjourney",
                                "flux", "veo", "kling", "pika", "comfyui", "diffusion", "gan",
                                "nerf", "gaussian splatting", "text-to-video", "text-to-image",
                                "image generation", "video generation", "generative video",
                                "generative media", "generative ai"],
            "strong_tech_keywords": ["machine learning", "deep learning", "computer vision",
                                     "research scientist", "phd", "icpc", "kaggle",
                                     "distributed systems", "infrastructure at scale"],
            "commercial_keywords": ["b2b", "b2c", "enterprise sales", "head of sales", "vp sales",
                                    "scaled revenue", "grew revenue", "commercial lead", "0 to 1"],
        },
        "tier2": {
            "us_startup_signals": ["y combinator", "yc", "series a", "series b", "seed",
                                   "san francisco", "bay area", "silicon valley", "startup"],
            "product_gtm_keywords": ["product manager", "product lead", "go-to-market", "growth",
                                     "partnerships", "business development"],
        },
        "exclusions": {
            "current_company": ["northwind"],
            "investor_terms": ["northwind investor", "invested in northwind"],
        },
    },
}
