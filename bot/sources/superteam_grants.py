"""Superteam Earn grants (Solana ecosystem; many are limited to one country)."""
from __future__ import annotations

import re

from ..http import client
from ..location import COUNTRY_RE, INDIA_RE
from ..models import Item

NAME = "superteam_grants"
URL = "https://superteam.fun/api/grants"
# "The Touching Grass Fund (India)" / "Solana Foundation India Grants"
PAREN_RE = re.compile(r"\(([^)]+)\)\s*$")
FOUNDATION_RE = re.compile(r"Solana Foundation (.+?) Grants?$", re.I)


def _num(v) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def region_of(title: str) -> str:
    m = PAREN_RE.search(title) or FOUNDATION_RE.search(title)
    if m:
        return m.group(1).strip()
    m = COUNTRY_RE.search(title) or INDIA_RE.search(title)  # "La Familia Spain Grants"
    return m.group(1) if m else ""


def parse(data) -> list[Item]:
    if isinstance(data, dict):
        data = data.get("grants") or data.get("data") or []
    items = []
    for g in data or []:
        if not isinstance(g, dict) or not g.get("slug") or not g.get("title"):
            continue
        lo, hi = _num(g.get("minReward")), _num(g.get("maxReward"))
        sponsor = g.get("sponsor") or {}
        region = region_of(g["title"])
        desc = "\n".join(filter(None, [
            f"Location: {region}" if region else "",
            f"Grant size: {lo or 0:,.0f}-{hi or 0:,.0f} {g.get('token', '')}",
            f"Applications so far: {g.get('totalApplications', 'n/a')}; approved total: {g.get('approvedAmountTotal', 'n/a')}",
        ]))
        items.append(Item(
            source=NAME,
            kind="grant",
            external_id=g["slug"],
            title=g["title"],
            org=sponsor.get("name", "") if isinstance(sponsor, dict) else "",
            url=f"https://superteam.fun/earn/grants/{g['slug']}",
            description=desc,
            pay_min=lo or None,
            pay_max=hi or None,
            pay_currency=g.get("token") or "",
            pay_unit="fixed" if hi else "unknown",
            tags=["solana"],
        ))
    return items


def fetch(cfg: dict | None = None) -> list[Item]:
    with client() as c:
        r = c.get(URL)
        r.raise_for_status()
        return parse(r.json())
