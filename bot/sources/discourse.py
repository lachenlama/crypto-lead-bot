"""DAO Discourse forums: latest topics filtered by lead keywords."""
from __future__ import annotations

import logging

from ..http import client
from ..models import Item

log = logging.getLogger(__name__)
NAME = "discourse"
DEFAULT_KEYWORDS = [
    "treasury", "diversification", "yield", "asset management",
    "grants", "grant", "rfp", "tooling", "analytics", "dashboard",
]


def matches_keywords(text: str, keywords: list[str] | None = None) -> bool:
    t = text.lower()
    return any(k.lower() in t for k in (keywords or DEFAULT_KEYWORDS))


def parse(data: dict, forum: str, keywords: list[str] | None = None) -> list[Item]:
    topics = ((data or {}).get("topic_list") or {}).get("topics") or []
    items = []
    for t in topics:
        title = t.get("title") or ""
        if not title or not matches_keywords(title, keywords):
            continue
        items.append(
            Item(
                source=f"discourse:{forum}",
                kind="lead",
                external_id=str(t["id"]),
                title=title,
                org=forum,
                url=f"https://{forum}/t/{t.get('slug', '')}/{t['id']}",
                posted_at=t.get("created_at", "") or "",
            )
        )
    return items


def fetch(cfg: dict | None = None) -> list[Item]:
    cfg = cfg or {}
    items: list[Item] = []
    failed = 0
    with client() as c:
        for forum in cfg.get("forums") or []:
            try:
                r = c.get(f"https://{forum}/latest.json")
                r.raise_for_status()
                items.extend(parse(r.json(), forum, cfg.get("lead_keywords")))
            except Exception as e:
                failed += 1
                log.warning("forum %s failed: %s", forum, e)
    forums = cfg.get("forums") or []
    if failed and failed == len(forums):
        raise RuntimeError("all forums failed")
    return items
