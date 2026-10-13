"""Rule-based scoring against the profile, optionally refined by Claude."""
from __future__ import annotations

import logging
import re

from . import llm
from .models import Item

log = logging.getLogger(__name__)
STABLE = {"", "USD", "USDC", "USDT", "DAI"}
HOURS_PER_YEAR = 2000


def _hits(text: str, words: list[str]) -> list[str]:
    out = []
    for w in words:
        if re.search(r"(?<![a-z0-9])" + re.escape(w.lower()) + r"(?![a-z0-9])", text):
            out.append(w)
    return out


def pay_vs_floor(item: Item, profile: dict) -> str | None:
    """Return 'above', 'below' or None (unknown / not comparable)."""
    if not item.has_pay or item.pay_currency.upper() not in STABLE:
        return None
    top = max(item.pay_min or 0, item.pay_max or 0)
    floor = profile.get("rate_floor", {})
    if item.pay_unit == "hour":
        ref = floor.get("hour", 60)
    elif item.pay_unit == "year":
        ref = floor.get("hour", 60) * HOURS_PER_YEAR
    elif item.pay_unit == "fixed":
        ref = floor.get("fixed", 600)
    else:
        return None
    return "above" if top >= ref else "below"


META_TAGS = {"target", "tier1", "tier2", "ai_eval"}
TIER_BOOST = {"tier1": 15, "tier2": 8}
BASE = 20
NO_MATCH_CAP = 35  # nothing relevant matched: must stay well below the digest threshold
REMOTE_WORDS = ["remote", "contract", "freelance", "contractor"]


def target_boost(item: Item) -> int:
    return max((v for k, v in TIER_BOOST.items() if k in item.tags), default=0)


def rule_score(item: Item, profile: dict) -> tuple[int, str]:
    tags = [t for t in item.tags if t not in META_TAGS]
    text = " ".join([item.title, item.description, " ".join(tags)]).lower()
    title = item.title.lower()
    score, why = BASE, []
    matched = False

    # skills in the title count a lot; mentions only in the description/tags count a little
    pri_words = profile.get("priority_skills", [])
    pri_title = _hits(title, pri_words)
    pri_body = [w for w in _hits(text, pri_words) if w not in pri_title]
    if pri_title:
        score += min(len(pri_title) * 25, 50)
    if pri_body:
        score += min(len(pri_body) * 5, 10)
    if pri_title or pri_body:
        matched = True
        why.append("skills: " + ", ".join((pri_title + pri_body)[:4]))
    sec = _hits(text, profile.get("secondary_skills", []))
    if sec:
        matched = True
        score += min(len(sec) * 4, 8)
        why.append("secondary: " + ", ".join(sec[:3]))
    bonus_title = _hits(title, profile.get("bonus_keywords", []))
    bonus = bonus_title or (
        _hits(text, profile.get("bonus_keywords", [])) if item.kind == "lead" else []
    )
    if bonus:
        matched = True
        score += 30 if bonus_title else 15
        why.append("analyst/treasury fit")
    if "ai_eval" in item.tags:
        matched = True
        score += 25
        why.append("AI eval vendor")
        ev = _hits(title, profile.get("ai_eval_keywords", []))
        if ev:
            score += 15
            why.append("eval role: " + ", ".join(ev[:2]))
        if _hits(text, REMOTE_WORDS):
            score += 10
            why.append("remote/contract")
        dom = _hits(text, profile.get("ai_eval_domain_keywords", []))
        if dom:
            score += 10
            why.append("domain eval: " + ", ".join(dom[:2]))
    # owner has ~2 years of experience: senior titles and language-specific roles are poor fits
    senior = _hits(title, profile.get("seniority_keywords", []))
    if senior:
        score -= 30
        why.append("too senior: " + ", ".join(senior[:2]))
    lang = _hits(title, profile.get("language_role_keywords", []))
    if lang:
        score -= 35
        why.append("language-specific role: " + ", ".join(lang[:2]))
    avoid = _hits(title, profile.get("avoid_keywords", []))
    if avoid:
        score -= 25
        why.append("avoid: " + ", ".join(avoid[:2]))
    if not matched:
        score = min(score, NO_MATCH_CAP)
    elif item.kind == "lead":
        score += 5
    pay = pay_vs_floor(item, profile)
    if pay == "below":
        score -= 15
        why.append("pay below floor")
    elif pay == "above" and matched:
        score += 10
        why.append("pay above floor")
    score = max(0, min(100, score))
    return score, "; ".join(why) or "no profile keywords matched"


def score_items(items: list[Item], profile: dict, cfg: dict | None = None) -> None:
    """Set score / score_reason / package on each item (in place)."""
    for it in items:
        it.score, it.score_reason = rule_score(it, profile)
    if llm.available() and items:
        _llm_refine(items, profile, cfg)
    for it in items:  # target-company boost applies to the final score
        boost = target_boost(it)
        if boost:
            it.score = min(100, (it.score or 0) + boost)
            it.score_reason += f"; target company +{boost}"
        cap, why = fit_cap(it, profile)
        if cap is not None and (it.score or 0) > cap:
            it.score = cap
            it.score_reason += f"; capped at {cap} ({why})"


def fit_cap(item: Item, profile: dict) -> tuple[int | None, str]:
    """Hard ceiling for roles the owner can't realistically get: senior titles stay out of instant
    alerts (digest at most), language-specific roles are effectively dropped."""
    title = item.title.lower()
    if _hits(title, profile.get("language_role_keywords", [])):
        return 40, "language-specific role"
    if _hits(title, profile.get("seniority_keywords", [])):
        return 60, "senior title"
    return None, ""


def _llm_refine(items: list[Item], profile: dict, cfg: dict | None) -> None:
    cfg = cfg or {}
    batch = int(cfg.get("thresholds", {}).get("llm_batch_size", 10))
    model = llm.model_for("score", cfg)
    for i in range(0, len(items), batch):
        chunk = items[i : i + batch]
        try:
            results = llm.score_batch(chunk, profile, model)
        except Exception as e:
            log.warning("LLM scoring failed, keeping rule scores: %s", type(e).__name__)
            continue
        for idx, res in results.items():
            if 0 <= idx < len(chunk):
                it = chunk[idx]
                it.score = round(0.7 * res["score"] + 0.3 * (it.score or 0))
                it.score_reason = res["reason"] or it.score_reason
                it.package = res["package"]
