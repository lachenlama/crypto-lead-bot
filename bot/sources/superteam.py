"""Superteam Earn listings (bounties / projects)."""
from __future__ import annotations

from ..http import client
from ..models import Item

NAME = "superteam"
URL = "https://superteam.fun/api/listings"


def _num(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def parse(data) -> list[Item]:
    if isinstance(data, dict):  # tolerate wrapped responses
        data = data.get("listings") or data.get("data") or []
    items = []
    for row in data:
        if not isinstance(row, dict):
            continue
        if row.get("status") != "OPEN":
            continue
        if row.get("agentAccess") == "AGENT_ONLY":
            continue
        slug = row.get("slug")
        if not slug or not row.get("title"):
            continue
        amount = _num(row.get("rewardAmount"))
        token = row.get("token") or ""
        sponsor = row.get("sponsor") or {}
        items.append(
            Item(
                source=NAME,
                kind="gig",
                external_id=str(row.get("id") or slug),
                title=row["title"],
                org=sponsor.get("name", "") if isinstance(sponsor, dict) else "",
                url=f"https://superteam.fun/earn/listing/{slug}",
                description=f"Type: {row.get('type', '')}. Compensation: {row.get('compensationType', '')}.",
                pay_min=amount,
                pay_max=amount,
                pay_currency=token,
                pay_unit="fixed" if amount else "unknown",
                deadline=row.get("deadline", "") or "",
                tags=[t for t in [row.get("type")] if t],
            )
        )
    return items


def fetch(cfg: dict | None = None) -> list[Item]:
    with client() as c:
        r = c.get(URL)
        r.raise_for_status()
        return parse(r.json())
