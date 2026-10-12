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


def rule_score(item: Item, profile: dict) -> tuple[int, str]:
    text = " ".join([item.title, item.description, " ".join(item.tags)]).lower()
    title = item.title.lower()
    score, why = 20, []

    pri = _hits(text, profile.get("priority_skills", []))
    if pri:
        score += min(len(pri) * 10, 40)
        why.append("skills: " + ", ".join(pri[:4]))
    sec = _hits(text, profile.get("secondary_skills", []))
    if sec:
        score += min(len(sec) * 4, 8)
        why.append("secondary: " + ", ".join(sec[:3]))
    bonus = _hits(title, profile.get("bonus_keywords", [])) or (
        _hits(text, profile.get("bonus_keywords", [])) if item.kind == "lead" else []
    )
    if bonus:
        score += 15
        why.append("analyst/treasury fit")
    avoid = _hits(title, profile.get("avoid_keywords", []))
    if avoid:
        score -= 25
        why.append("avoid: " + ", ".join(avoid[:2]))
    if item.kind == "lead":
        score += 5
    pay = pay_vs_floor(item, profile)
    if pay == "below":
        score -= 15
        why.append("pay below floor")
    elif pay == "above":
        score += 10
        why.append("pay above floor")
    score = max(0, min(100, score))
    return score, "; ".join(why) or "no profile keywords matched"


def score_items(items: list[Item], profile: dict, cfg: dict | None = None) -> None:
    """Set score / score_reason / package on each item (in place)."""
    for it in items:
        it.score, it.score_reason = rule_score(it, profile)
    if not llm.available() or not items:
        return
    cfg = cfg or {}
    batch = int(cfg.get("thresholds", {}).get("llm_batch_size", 10))
    model = cfg.get("models", {}).get("scoring", llm.SCORING_MODEL)
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
