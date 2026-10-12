"""cryptocurrencyjobs.co RSS feed."""
from __future__ import annotations

import html

import feedparser

from ..http import client
from ..models import Item, clean_text

NAME = "cryptocurrencyjobs"
URL = "https://cryptocurrencyjobs.co/index.xml"


def _unescape2(s: str) -> str:
    # Titles may be double-escaped (&amp;amp;).
    return html.unescape(html.unescape(s or "")).strip()


def parse(xml: str | bytes) -> list[Item]:
    feed = feedparser.parse(xml)
    items = []
    for e in feed.entries:
        title = _unescape2(e.get("title", ""))
        if not title:
            continue
        link = e.get("link", "")
        items.append(
            Item(
                source=NAME,
                kind="job",
                external_id=e.get("id") or e.get("guid") or link,
                title=title,
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
