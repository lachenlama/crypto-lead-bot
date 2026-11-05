"""Devpost hackathons (public JSON API), filtered by theme, sorted by prize."""
from __future__ import annotations

import logging

from ..events import end_date, parse_money
from ..http import client
from ..models import Item, clean_text

log = logging.getLogger(__name__)
NAME = "devpost"
URL = "https://devpost.com/api/hackathons"
DEFAULT_THEMES = ["Blockchain", "Machine Learning/AI", "Fintech"]
PAGES = 2  # 9 per page, sorted by prize amount


def parse(data: dict) -> list[Item]:
    items = []
    for h in (data or {}).get("hackathons") or []:
        if not isinstance(h, dict) or not h.get("title") or not h.get("url"):
            continue
        if h.get("invite_only"):
            continue
        amount, cur = parse_money(clean_text(h.get("prize_amount") or ""))
        cash = (h.get("prizes_counts") or {}).get("cash", 0)
        if not amount and not cash:  # paid work only: no cash prizes, skip
            continue
        loc = ((h.get("displayed_location") or {}).get("location") or "").strip()
        themes = [t.get("name", "") for t in h.get("themes") or [] if isinstance(t, dict)]
        dates = h.get("submission_period_dates") or ""
        desc = "\n".join([
            f"Location: {loc or 'not stated'}",
            f"Themes: {', '.join(themes)}",
            f"Submissions: {dates} ({h.get('time_left_to_submission', '')})",
            f"Registrations: {h.get('registrations_count', 'n/a')}",
        ])
        url = h["url"] if h["url"].startswith("http") else "https:" + h["url"]
        items.append(Item(
            source=NAME,
            kind="hackathon",
            external_id=str(h.get("id") or url),
            title=h["title"],
            org=h.get("organization_name") or "",
            url=url,
            description=desc,
            pay_min=amount or None,
            pay_max=amount or None,
            pay_currency=cur,
            pay_unit="fixed" if amount else "unknown",
            deadline=end_date(dates),
            tags=[t for t in themes if t],
        ))
    return items


def fetch(cfg: dict | None = None) -> list[Item]:
    themes = (cfg or {}).get("devpost_themes") or DEFAULT_THEMES
    seen, out = set(), []
    with client() as c:
        for theme in themes:
            for page in range(1, PAGES + 1):
                r = c.get(URL, params={"status[]": ["upcoming", "open"], "themes[]": theme,
                                       "order_by": "prize-amount", "page": page})
                r.raise_for_status()
                data = r.json()
                for it in parse(data):
                    if it.external_id not in seen:
                        seen.add(it.external_id)
                        out.append(it)
                if len(data.get("hackathons") or []) < 9:
                    break
    return out
