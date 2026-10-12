"""CryptoJobsList RSS feed (CDATA titles)."""
from __future__ import annotations

import html

import feedparser

from ..http import client
from ..models import Item, clean_text

NAME = "cryptojobslist"
URL = "https://api.cryptojobslist.com/jobs.rss"


def parse(xml: str | bytes) -> list[Item]:
    feed = feedparser.parse(xml)
    items = []
    for e in feed.entries:
        title = html.unescape(e.get("title", "")).strip()
        if not title:
            continue
        link = e.get("link", "")
        org = e.get("author", "") or ""
        items.append(
            Item(
                source=NAME,
                kind="job",
                external_id=e.get("id") or e.get("guid") or link,
                title=title,
                org=org,
                url=link,
                description=clean_text(e.get("description") or e.get("summary", "")),
                posted_at=e.get("published", ""),
                tags=[t.get("term", "") for t in e.get("tags", []) if t.get("term")],
            )
        )
    return items


def fetch(cfg: dict | None = None) -> list[Item]:
    with client() as c:
        r = c.get(URL)
        r.raise_for_status()
        return parse(r.content)
