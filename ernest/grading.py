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

# Scoring weights — the documented contract. The grading skills quote these
# tables and `tests/test_skill_contract.py` keeps the docs honest; if you tune
# ranking, tune it HERE (per-hit weights multiply by the number of distinct
# list hits — "signal density").
CRM_BASE = {"tier-1": 100.0, "other": 60.0}
DEFAULT_TIER2_SCORE = 2.0  # unknown-but-not-trash B2B default (needs a check)
B2B_WEIGHTS = {
    "category": 8.0,             # per ICP-category hit
    "provider": 12.0,            # per model/cloud-provider hit
    "company": 12.0,             # per major-company hit
    "person": 15.0,              # per high-reputation-person hit
    "intent": 6.0,               # per enterprise-intent keyword hit
    "reputation_or_prior": 14.0, # single bump: CEO reference OR CRM prior contact
    "large_fund": 15.0,          # fund AUM above rubric threshold
}
TALENT_WEIGHTS = {
    "senior_at_big_tech": 16.0,          # senior title AND big-tech company
    "strong_tech": 12.0,                 # per strong-technical-keyword hit
    "ai_media": 12.0,                    # per AI-media model/product hit
    "commercial_in_tier1_country": 14.0, # commercial signal AND Tier-1 country
    "t2_big_tech": 8.0,                  # tier-2: per big-tech hit alone
    "t2_us_startup": 5.0,                # tier-2: US-startup signal
    "t2_gtm": 5.0,                       # tier-2: product/GTM signal
    "t2_country": 2.0,                   # tier-2: country alone (never qualifying)
}

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
        base = CRM_BASE["tier-1"] if tier == "tier-1" else CRM_BASE["other"]
        return Grade(tier, "high", [f"CRM tier '{crm_tier}' -> {tier}"], [], base)

    # 2. Tier-1 list/intent signals — count ALL hits for density/score.
    cats = _all_in(hay, t1.get("categories", []))
    provs = _all_in(hay, t1.get("providers", []))
    comps = _all_in(hay, t1.get("companies", []))
    people = _all_in(hay, t1.get("people", []))
    intents = _all_in(hay, t1.get("intent_keywords", []))
    reps = _all_in(hay, t1.get("reputation_keywords", []))
    if cats:
        reasons.append(f"ICP category: {', '.join(cats[:3])}"); score += B2B_WEIGHTS["category"] * len(cats)
    if provs:
        reasons.append(f"Model/cloud provider: {', '.join(provs[:3])}"); score += B2B_WEIGHTS["provider"] * len(provs)
    if comps:
        reasons.append(f"Major company: {', '.join(comps[:3])}"); score += B2B_WEIGHTS["company"] * len(comps)
    if people:
        reasons.append(f"High-reputation person: {', '.join(people[:3])}"); score += B2B_WEIGHTS["person"] * len(people)
    if intents:
        reasons.append(f"Enterprise buying intent: {', '.join(intents[:3])}"); score += B2B_WEIGHTS["intent"] * len(intents)
    if reps or prior_contact:
        reasons.append("Prior contact (CRM)" if prior_contact else f"References the CEO: {', '.join(reps[:2])}")
        score += B2B_WEIGHTS["reputation_or_prior"]
    threshold = float(t1.get("fund_aum_threshold_busd", 2.0))
    if fund_aum_busd is not None and fund_aum_busd > threshold:
        reasons.append(f"Large fund: ~${fund_aum_busd}B AUM (> ${threshold}B)"); score += B2B_WEIGHTS["large_fund"]

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
    return Grade("tier-2", "low", ["No decisive signal; defaulting to Tier-2"], flags,
                 DEFAULT_TIER2_SCORE)


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
        reasons.append(f"Senior role ('{senior}') at {', '.join(big_tech[:2])}")
        score += TALENT_WEIGHTS["senior_at_big_tech"]; structural = True
    if strong_tech:
        reasons.append(f"Strong technical base: {', '.join(strong_tech[:3])}")
        score += TALENT_WEIGHTS["strong_tech"] * len(strong_tech); structural = True
    if ai_media:
        reasons.append(f"AI media products/models: {', '.join(ai_media[:3])}")
        score += TALENT_WEIGHTS["ai_media"] * len(ai_media); structural = True
    if commercial and country:
        reasons.append(f"Commercial strength ('{commercial}') in Tier-1 country ('{country.strip()}')")
        score += TALENT_WEIGHTS["commercial_in_tier1_country"]

    if reasons:
        confidence = "high" if structural else "medium"
        flags.append(f"Confirm they're likely interested in {pool} (judgment call).")
        return Grade("tier-1", confidence, reasons, flags, score)

    # Tier-2 signals — a single relevant signal is enough to surface as an option.
    t2_reasons: List[str] = []
    if big_tech:
        t2_reasons.append(f"Big Tech experience: {', '.join(big_tech[:2])}")
        score += TALENT_WEIGHTS["t2_big_tech"] * len(big_tech)
    us_startup = _any_in(hay, t2.get("us_startup_signals", []))
    if us_startup:
        t2_reasons.append(f"US startup signal: '{us_startup}'"); score += TALENT_WEIGHTS["t2_us_startup"]
    gtm = _any_in(hay, t2.get("product_gtm_keywords", []))
    if gtm:
        t2_reasons.append(f"Product/GTM experience: '{gtm}'"); score += TALENT_WEIGHTS["t2_gtm"]
    if ai_media:
        t2_reasons.append(f"Worked with AI media models: {', '.join(ai_media[:2])}")
    if country:
        score += TALENT_WEIGHTS["t2_country"]

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
    "linkedin": {
        # Deliberately thin. The real lists live in
        # data/grading/linkedin-rubric.json; this exists so a missing or
        # unparseable file degrades to "surface everything for a human" rather
        # than to silent confident answers — and so `ernest doctor` can name
        # which signal family a hand-edit turned off.
        "crm_tier_map": {"vip": "tier-1", "customer": "tier-1", "investor": "hold",
                         "partner": "tier-2"},
        "suppression": {"411": {"name": "Suppressed ALL (union)", "route": "hold",
                                "signal": "Do Not Contact"}},
        "hold": {"press_keywords": ["journalist", "reporter"],
                 "investor_keywords": ["general partner", "angel investor"],
                 "legal_or_regulatory_keywords": ["general counsel", "regulator"],
                 "competitor_keywords": [],
                 "exec_escalation_keywords": ["spoke with alex"]},
        "tier1": {"buyer_archetypes": [], "verticals": [], "platform_buyers": [],
                  "providers": [], "companies": [], "seniority_keywords": [],
                  "function_keywords": [], "intent_keywords": [],
                  "tier1_countries": [], "min_mutual_connections_signal": 5},
        "job_seeker": {"keywords": ["open to work", "#opentowork"]},
        "escalation": {"money_keywords": ["refund", "chargeback"],
                       "legal_keywords": ["cease and desist"],
                       "security_keywords": ["data breach"],
                       "churn_keywords": ["cancel our"],
                       "safety_keywords": ["harassment"]},
        "spam": {"vendor_keywords": [], "headline_keywords": [],
                 "template_fingerprints": [], "dm_blast_keywords": [],
                 "low_connection_threshold": 50,
                 "threshold": 5.0},   # must equal SPAM_THRESHOLD; tests assert it
        "signal_map": {"tier-1": "Positive", "tier-2": "None", "hold": "Positive",
                       "trash": "Spam", "vendor": "Seller Pitch",
                       "job_seeker": "JOB_SEEKER", "suppressed": "Do Not Contact"},
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


# --------------------------------------------------------------------------- #
# LinkedIn inbound grading
# --------------------------------------------------------------------------- #
#
# Surface: a pending connection invitation (or an opening DM) from a stranger.
# Unlike mail, there is no thread history and no CRM record for most of the
# population — the whole signal is a headline, an optional 300-char note, and the
# SHAPE of the sender's profile.
#
# The DECISION ORDER below is the safety mechanism and is not negotiable:
#
#     suppression -> hold -> CRM tier -> tier-1 signals -> job seeker
#                 -> spam -> default tier-2
#
# Checking tier before suppression is how a competitor or a journalist ends up
# accepted and then sequenced. Reordering these branches is a behavior change,
# not a refactor.

LINKEDIN_RANK = {"tier-1": 0, "hold": 1, "tier-2": 2, "trash": 3, "unknown": 4}

# Per-DISTINCT-hit weights (signal density: two independent signals beat one
# repeated). Documented in skills/linkedin-invitations/references/rubric.md and
# kept honest by tests/test_skill_contract.py.
LINKEDIN_WEIGHTS = {
    "buyer_archetype": 14.0,   # per buyer-archetype hit (AI studio, agency, production house)
    "vertical": 10.0,          # per won-revenue vertical hit
    "platform_buyer": 14.0,    # per API/white-label signal
    "provider": 12.0,          # per model/cloud-provider hit
    "company": 12.0,           # per major-company hit
    "seniority": 8.0,          # per decision-maker title hit
    "function": 4.0,           # per relevant-function hit
    "intent": 10.0,            # per buying-intent keyword in the note
    "reputation_or_prior": 16.0,  # single bump: CEO reference OR CRM prior contact
    "mutuals": 6.0,            # single bump: mutual connections above rubric floor
    "tier1_country": 3.0,      # single bump: a country we actually close in
}

# Spam is scored, not matched — one template phrase is not proof of anything.
# A sender needs SPAM_THRESHOLD points of independent structural evidence.
LINKEDIN_SPAM_WEIGHTS = {
    "vendor_phrase": 4.0,      # per distinct cold-vendor phrase in the note
    "spam_headline": 3.0,      # per distinct spam-headline pattern
    "template_note": 2.0,      # per distinct mass-template fingerprint
    "no_mutuals": 1.5,         # zero mutual connections
    "thin_network": 2.0,       # connection count below the rubric floor
    "empty_note": 0.5,         # no note at all on a cold invite
}
# Default only. The live value is `spam.threshold` in the rubric JSON, so the
# improve loop has a knob to turn when the override rate says we are too eager.
SPAM_THRESHOLD = 5.0


@dataclass
class LinkedInGrade(Grade):
    """A Grade plus the two fields HubSpot already models for this surface.

    `signal` emits `linkedin_message_signal` VERBATIM
    (Positive | Negative | Seller Pitch | JOB_SEEKER | Do Not Contact | Spam | None)
    and `action` is the only thing the report is allowed to propose.
    """
    signal: str = "None"
    action: str = "Review"

    @property
    def rank(self) -> int:  # type: ignore[override]
        return LINKEDIN_RANK.get(self.tier, 4)


def _signal_for(rubric: dict, key: str) -> str:
    return (rubric.get("signal_map") or {}).get(key, "None")


def identity_key(public_url: str = "", urn: str = "", name: str = "") -> str:
    """Stable dedup key across LinkedIn's two identifier shapes.

    HubSpot's own `linkedin_identity_key` field description records the problem:
    the same human arrives once by public slug and once by member URN
    (`ACoAA...`), so keying on either alone double-counts them. Prefer the slug,
    fall back to the URN, fall back to a normalized name.
    """
    slug = ""
    if public_url:
        m = re.search(r"/in/([^/?#]+)", public_url.strip().rstrip("/"), re.I)
        slug = (m.group(1) if m else public_url.strip().rstrip("/").rsplit("/", 1)[-1]).lower()
    if slug:
        return f"slug:{slug}"
    if urn:
        return f"urn:{urn.strip().lower()}"
    return f"name:{re.sub(r'[^a-z0-9]+', '-', name.strip().lower()).strip('-')}"


def grade_linkedin_inbound(
    *,
    name: str = "",
    headline: str = "",
    note: str = "",
    company: str = "",
    location: str = "",
    mutual_connections: Optional[int] = None,
    connections: Optional[int] = None,
    crm_tier: str = "",
    suppression_lists: Optional[List[str]] = None,
    prior_contact: bool = False,
    cfg: Optional[Config] = None,
) -> LinkedInGrade:
    """Tier one pending invitation. Read-only: proposes an action, never takes one.

    `mutual_connections` / `connections` are Optional on purpose — `None` means
    "we did not look", which is not the same as 0 and must never be scored as
    evidence of a thin network. Missing != 0.
    """
    r = _load_rubric(cfg, "linkedin")
    hay = _hay(headline, note, company, location, name)
    flags: List[str] = []

    # 1. SUPPRESSION — before any tier is assigned. The order is the safety rule.
    supp = r.get("suppression", {})
    for list_id in (suppression_lists or []):
        entry = supp.get(str(list_id))
        if not entry:
            continue
        route = entry.get("route", "hold")
        reason = f"On HubSpot list {list_id} ({entry.get('name', 'suppressed')})"
        if route == "accept":
            return LinkedInGrade("tier-1", "high", [reason], flags, CRM_BASE["other"],
                                 signal=entry.get("signal", "None"), action="Accept")
        if route == "drop":
            return LinkedInGrade("trash", "high", [reason], flags, 0.0,
                                 signal=entry.get("signal", "None"), action="Ignore")
        return LinkedInGrade("hold", "high", [reason], flags, 0.0,
                             signal=entry.get("signal", _signal_for(r, "suppressed")),
                             action="Hold — suppressed list, decide by hand")

    # 2. HOLD — press, investors, legal, competitors, exec references. Never
    #    auto-resolved in either direction. Press is high-stakes here, not trash.
    hold = r.get("hold", {})
    for key, label, signal, action in (
        ("competitor_keywords", "Competitor", "Do Not Contact",
         "Hold — do not accept unread"),
        ("legal_or_regulatory_keywords", "Legal/regulatory", "Do Not Contact",
         "Hold — route to legal, never answer from here"),
        ("press_keywords", "Press/journalist", "Positive",
         "Hold — route to comms, do not ignore"),
        ("investor_keywords", "Investor", "Positive",
         "Hold — the CEO decides personally"),
        ("exec_escalation_keywords", "Claims a prior conversation with the CEO", "Positive",
         "Hold — verify the claim before accepting"),
    ):
        hit = _any_in(hay, hold.get(key, []))
        if hit:
            return LinkedInGrade("hold", "medium", [f"{label}: '{hit}'"], flags, 0.0,
                                 signal=signal, action=action)

    # 3. CRM tier — a known relationship outranks anything inferred from a headline.
    crm_map = {k.lower(): v for k, v in (r.get("crm_tier_map") or {}).items()}
    if crm_tier and crm_tier.lower() in crm_map:
        tier = crm_map[crm_tier.lower()]
        base = CRM_BASE["tier-1"] if tier == "tier-1" else CRM_BASE["other"]
        action = "Accept" if tier in ("tier-1", "tier-2") else "Hold — known relationship"
        return LinkedInGrade(tier, "high", [f"CRM tier '{crm_tier}' -> {tier}"], flags, base,
                             signal=_signal_for(r, tier), action=action)

    # 4. TIER-1 SIGNALS — scored by density.
    t1 = r.get("tier1", {})
    score = 0.0
    reasons: List[str] = []

    def add(key: str, listname: str, label: str) -> List[str]:
        nonlocal score
        hits = _all_in(hay, t1.get(listname, []))
        if hits:
            reasons.append(f"{label}: {', '.join(hits[:3])}")
            score += LINKEDIN_WEIGHTS[key] * len(hits)
        return hits

    archetypes = add("buyer_archetype", "buyer_archetypes", "Buyer archetype")
    verticals = add("vertical", "verticals", "Won-revenue vertical")
    platform = add("platform_buyer", "platform_buyers", "Platform/API buyer")
    provs = add("provider", "providers", "Model/cloud provider")
    comps = add("company", "companies", "Major company")
    senior = add("seniority", "seniority_keywords", "Decision-maker title")
    add("function", "function_keywords", "Relevant function")
    intents = add("intent", "intent_keywords", "Buying intent in the note")

    if prior_contact:
        reasons.append("Already known to us (CRM prior contact)")
        score += LINKEDIN_WEIGHTS["reputation_or_prior"]

    floor = t1.get("min_mutual_connections_signal", 5)
    if mutual_connections is not None and mutual_connections >= floor:
        reasons.append(f"{mutual_connections} mutual connections (>= {floor})")
        score += LINKEDIN_WEIGHTS["mutuals"]

    country = _any_in(hay, t1.get("tier1_countries", []))
    if country:
        reasons.append(f"Country we close in: '{country}'")
        score += LINKEDIN_WEIGHTS["tier1_country"]

    # A title alone is not a buyer. Tier-1 requires a WHO (archetype/vertical/
    # platform/provider/company) — seniority and country only amplify it.
    structural = bool(archetypes or verticals or platform or provs or comps)
    if structural and (senior or intents or score >= 24.0):
        return LinkedInGrade("tier-1", "high" if (senior and intents) else "medium",
                             reasons, flags, score,
                             signal=_signal_for(r, "tier-1"), action="Accept")

    # 5. JOB SEEKER — not a buyer and not spam. Its own lane.
    js = _any_in(hay, (r.get("job_seeker") or {}).get("keywords", []))
    if js:
        flags.append("Route to the talent rubric if the profile is strong; otherwise decline politely.")
        return LinkedInGrade("tier-2", "medium", [f"Job seeker: '{js}'"], flags, 1.0,
                             signal=_signal_for(r, "job_seeker"),
                             action="Hold — talent lane, not a buyer")

    # 6. SPAM — scored, never matched on a single phrase. Structural evidence only.
    sp = r.get("spam", {})
    spam_score = 0.0
    spam_reasons: List[str] = []
    vendors = _all_in(hay, sp.get("vendor_keywords", []))
    if vendors:
        spam_reasons.append(f"Cold vendor pitch: {', '.join(vendors[:3])}")
        spam_score += LINKEDIN_SPAM_WEIGHTS["vendor_phrase"] * len(vendors)
    heads = _all_in(hay, sp.get("headline_keywords", []))
    if heads:
        spam_reasons.append(f"Spam headline pattern: {', '.join(heads[:3])}")
        spam_score += LINKEDIN_SPAM_WEIGHTS["spam_headline"] * len(heads)
    templates = _all_in(hay, sp.get("template_fingerprints", []))
    if templates:
        spam_reasons.append(f"Mass-template note: '{templates[0]}'")
        spam_score += LINKEDIN_SPAM_WEIGHTS["template_note"] * len(templates)
    if mutual_connections == 0:
        spam_reasons.append("No mutual connections")
        spam_score += LINKEDIN_SPAM_WEIGHTS["no_mutuals"]
    thin = sp.get("low_connection_threshold", 50)
    if connections is not None and connections < thin:
        spam_reasons.append(f"Thin network ({connections} < {thin} connections)")
        spam_score += LINKEDIN_SPAM_WEIGHTS["thin_network"]
    if not note.strip() and (vendors or heads):
        spam_reasons.append("No note on a cold invite")
        spam_score += LINKEDIN_SPAM_WEIGHTS["empty_note"]

    threshold = float(sp.get("threshold", SPAM_THRESHOLD) or SPAM_THRESHOLD)
    if spam_score >= threshold:
        signal = _signal_for(r, "vendor") if vendors or heads else _signal_for(r, "trash")
        return LinkedInGrade("trash", "high" if spam_score >= threshold * 1.6 else "medium",
                             spam_reasons, flags, spam_score,
                             signal=signal, action="Ignore")

    # 7. DEFAULT — tier-2, low confidence, flagged. Never a silent tier-1 and
    #    never a silent trash: an ambiguous stranger is surfaced, not deleted.
    if spam_reasons:
        flags.append(f"Some spam signal ({spam_score:.1f} < {threshold:g} threshold), "
                     f"not enough to ignore: {'; '.join(spam_reasons[:2])}. "
                     "Read the note before deciding.")
    if reasons:
        flags.append("ICP-adjacent but no decisive buyer signal; verify before upgrading.")
        return LinkedInGrade("tier-2", "medium", reasons, flags, score,
                             signal=_signal_for(r, "tier-2"), action="Review")
    flags.append("No ICP hit and not obvious spam. Unknown stranger — decide by hand or leave pending.")
    return LinkedInGrade("tier-2", "low", ["No decisive signal; defaulting to Tier-2"], flags,
                         DEFAULT_TIER2_SCORE, signal=_signal_for(r, "tier-2"), action="Review")


# --------------------------------------------------------------------------- #
# LinkedIn direct messages
# --------------------------------------------------------------------------- #
#
# An invitation asks "who is this". A DM asks a different first question: "am I
# the one holding this up". A thread we have answered before is a relationship,
# and a relationship is never spam no matter what the words look like.
#
# ORDER (again, the safety mechanism):
#
#   escalation -> hold -> replied-before -> owed+ICP -> job seeker -> spam -> FYI
#
# `escalation` runs first and outranks everything, including our own prior
# replies: a refund dispute or a security report from a long-standing contact is
# MORE urgent than one from a stranger, not less.

LINKEDIN_DM_RANK = {"escalation": 0, "needs-reply": 1, "hold": 2,
                    "fyi": 3, "trash": 4, "unknown": 5}

LINKEDIN_DM_WEIGHTS = {
    "owed": 12.0,           # they wrote last and we never answered
    "relationship": 18.0,   # we have replied in this thread before
    "icp": 10.0,            # per ICP signal in what they wrote
    "intent": 12.0,         # per buying-intent keyword
    "question": 4.0,        # they asked something answerable
    "waiting_week": 2.0,    # per week waiting, capped
}
DM_WAITING_CAP = 8


@dataclass
class LinkedInDMGrade(Grade):
    """Grade plus the bucket, the HubSpot signal, and the proposed action."""
    bucket: str = "fyi"     # escalation | needs-reply | hold | fyi | trash
    signal: str = "None"
    action: str = "Read"

    @property
    def rank(self) -> int:  # type: ignore[override]
        return LINKEDIN_DM_RANK.get(self.bucket, 5)


def grade_linkedin_dm(
    *,
    counterparty: str = "",
    text: str = "",
    opener: str = "",
    headline: str = "",
    subject: str = "",
    folder: str = "INBOX",
    owed: bool = False,
    ever_replied: bool = False,
    days_waiting: int = 0,
    message_count: int = 1,
    crm_tier: str = "",
    suppression_lists: Optional[List[str]] = None,
    prior_contact: bool = False,
    cfg: Optional[Config] = None,
) -> LinkedInDMGrade:
    """Triage one message thread. Read-only: proposes an action, never takes one."""
    r = _load_rubric(cfg, "linkedin")
    hay = _hay(text, subject, headline, counterparty)
    flags: List[str] = []

    # 0. ESCALATION — the dozen things automation must never answer alone.
    #    Checked before everything, including our own prior replies.
    esc = r.get("escalation", {})
    for key, label in (("money_keywords", "Money or billing"),
                       ("legal_keywords", "Legal or contractual"),
                       ("security_keywords", "Security or data"),
                       ("churn_keywords", "Churn or cancellation"),
                       ("safety_keywords", "Safety or abuse")):
        hit = _any_in(hay, esc.get(key, []))
        if hit:
            flags.append("Automation must not answer this alone.")
            return LinkedInDMGrade("tier-1", "high", [f"{label}: '{hit}'"], flags, 100.0,
                                   bucket="escalation", signal="Positive",
                                   action="Answer personally — do not delegate or template")

    # 1. SUPPRESSION and 2. HOLD reuse the invitation rubric: the same person is
    #    the same person whether they invited us or messaged us.
    supp = r.get("suppression", {})
    for list_id in (suppression_lists or []):
        entry = supp.get(str(list_id))
        if entry and entry.get("route") != "accept":
            return LinkedInDMGrade("hold", "high",
                                   [f"On HubSpot list {list_id} ({entry.get('name', 'suppressed')})"],
                                   flags, 0.0, bucket="hold",
                                   signal=entry.get("signal", "Do Not Contact"),
                                   action="Hold — suppressed list, decide by hand")
    hold = r.get("hold", {})
    for key, label, signal, action in (
        ("competitor_keywords", "Competitor", "Do Not Contact", "Hold — do not answer from here"),
        ("legal_or_regulatory_keywords", "Legal/regulatory", "Do Not Contact", "Hold — route to legal"),
        ("press_keywords", "Press/journalist", "Positive", "Hold — route to comms, do not ignore"),
        ("investor_keywords", "Investor", "Positive", "Hold — the CEO decides personally"),
    ):
        hit = _any_in(hay, hold.get(key, []))
        if hit:
            return LinkedInDMGrade("hold", "medium", [f"{label}: '{hit}'"], flags, 0.0,
                                   bucket="hold", signal=signal, action=action)

    # 3. A THREAD WE HAVE ANSWERED is a relationship. It can be low priority, but
    #    it is never spam — this is the branch that stops the filter embarrassing
    #    us with someone we already talked to.
    reasons: List[str] = []
    score = 0.0
    if ever_replied:
        reasons.append("We have replied in this thread before")
        score += LINKEDIN_DM_WEIGHTS["relationship"]
    if crm_tier:
        crm_map = {k.lower(): v for k, v in (r.get("crm_tier_map") or {}).items()}
        mapped = crm_map.get(crm_tier.lower())
        if mapped:
            reasons.append(f"CRM tier '{crm_tier}'")
            score += CRM_BASE["tier-1"] if mapped == "tier-1" else CRM_BASE["other"]
    if prior_contact:
        reasons.append("Known to us in the CRM")
        score += LINKEDIN_DM_WEIGHTS["relationship"]

    # 4. ICP and intent, same lists as invitations.
    t1 = r.get("tier1", {})
    for key, listname, label in (("icp", "buyer_archetypes", "Buyer archetype"),
                                 ("icp", "verticals", "Vertical"),
                                 ("icp", "platform_buyers", "Platform/API"),
                                 ("icp", "companies", "Major company"),
                                 ("intent", "intent_keywords", "Buying intent")):
        hits = _all_in(hay, t1.get(listname, []))
        if hits:
            reasons.append(f"{label}: {', '.join(hits[:3])}")
            score += LINKEDIN_DM_WEIGHTS[key] * len(hits)
    if owed:
        reasons.append("They wrote last; no reply from us")
        score += LINKEDIN_DM_WEIGHTS["owed"]
        score += LINKEDIN_DM_WEIGHTS["waiting_week"] * min(days_waiting // 7, DM_WAITING_CAP)
    if "?" in text:
        reasons.append("They asked a question")
        score += LINKEDIN_DM_WEIGHTS["question"]

    # 5. SPAM — scored, and only ever for threads we have NEVER answered. The
    #    OPENER is what gets scored, not the whole thread: quoting a pitch back
    #    while declining it must not make the thread look like the pitch.
    sp = r.get("spam", {})
    threshold = float(sp.get("threshold", SPAM_THRESHOLD) or SPAM_THRESHOLD)
    if not ever_replied and not prior_contact:
        spam_hay = _hay(opener or text, headline)
        spam_reasons: List[str] = []
        spam_score = 0.0
        vendors = _all_in(spam_hay, sp.get("vendor_keywords", []))
        if vendors:
            spam_reasons.append(f"Cold pitch: {', '.join(vendors[:3])}")
            spam_score += LINKEDIN_SPAM_WEIGHTS["vendor_phrase"] * len(vendors)
        heads = _all_in(spam_hay, sp.get("headline_keywords", []))
        if heads:
            spam_reasons.append(f"Spam headline: {', '.join(heads[:2])}")
            spam_score += LINKEDIN_SPAM_WEIGHTS["spam_headline"] * len(heads)
        templates = _all_in(spam_hay, sp.get("template_fingerprints", []))
        if templates:
            spam_reasons.append(f"Mass template: '{templates[0]}'")
            spam_score += LINKEDIN_SPAM_WEIGHTS["template_note"] * len(templates)
        blasts = _all_in(spam_hay, sp.get("dm_blast_keywords", []))
        if blasts:
            spam_reasons.append(f"Sequence blast: '{blasts[0]}'")
            spam_score += LINKEDIN_SPAM_WEIGHTS["vendor_phrase"] * len(blasts)
        if folder.upper() == "SPAM":
            spam_reasons.append("LinkedIn already filed it as spam")
            spam_score += LINKEDIN_SPAM_WEIGHTS["spam_headline"]
        # A one-shot pitch nobody answered is the classic shape.
        if message_count == 1 and (vendors or heads or blasts):
            spam_reasons.append("Single unanswered cold message")
            spam_score += LINKEDIN_SPAM_WEIGHTS["no_mutuals"]
        # Guard on RELATIONSHIP evidence, never on the accumulated score. `score`
        # includes owed and waiting-time points, so guarding on it meant the
        # longer a cold pitch sat ignored the better it escaped the filter —
        # exactly backwards. Prior replies and prior contact are already excluded
        # by the enclosing branch; a CRM tier is the remaining relationship.
        if spam_score >= threshold and not crm_tier:
            return LinkedInDMGrade("trash",
                                   "high" if spam_score >= threshold * 1.6 else "medium",
                                   spam_reasons, flags, spam_score, bucket="trash",
                                   signal=_signal_for(r, "vendor") if (vendors or heads or blasts)
                                   else _signal_for(r, "trash"),
                                   action="Archive")
        if spam_reasons:
            flags.append(f"Some spam signal ({spam_score:.1f} < {threshold:g}): "
                         f"{'; '.join(spam_reasons[:2])}.")

    # 6. JOB SEEKER — its own lane, never spam.
    js = _any_in(hay, (r.get("job_seeker") or {}).get("keywords", []))
    if js and not ever_replied:
        return LinkedInDMGrade("tier-2", "medium", [f"Job seeker: '{js}'"], flags, score,
                               bucket="fyi", signal=_signal_for(r, "job_seeker"),
                               action="Forward to recruiting, or decline politely")

    # 7. OWED -> needs a reply. Not owed -> FYI.
    if owed:
        conf = "high" if score >= 30 else "medium" if score >= 12 else "low"
        if score < 12:
            flags.append("Owed but no strong signal — worth a look, not urgent.")
        return LinkedInDMGrade("tier-1" if score >= 30 else "tier-2", conf,
                               reasons or ["They wrote last; no reply from us"], flags, score,
                               bucket="needs-reply", signal=_signal_for(r, "tier-1")
                               if score >= 30 else "None",
                               action="Reply" if score >= 12 else "Reply or archive")
    return LinkedInDMGrade("tier-2", "low", reasons or ["Nothing owed; no action"], flags, score,
                           bucket="fyi", signal="None", action="Read")
