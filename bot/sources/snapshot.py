"""Snapshot active proposals as DAO treasury leads."""
from __future__ import annotations

from ..http import client
from ..models import Item, clean_text
from .discourse import matches_keywords

NAME = "snapshot"
URL = "https://hub.snapshot.org/graphql"
QUERY = """
query {
  proposals(first: 50, where: {state: "active"}, orderBy: "created", orderDirection: desc) {
    id title body link created end space { id name }
  }
}
"""


def _iso(ts) -> str:
    from datetime import datetime, timezone

    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (TypeError, ValueError):
        return ""


def parse(data: dict, keywords: list[str] | None = None) -> list[Item]:
    proposals = ((data or {}).get("data") or {}).get("proposals") or []
    items = []
    for p in proposals:
        title = p.get("title") or ""
        body = (p.get("body") or "")[:1500]
        if not matches_keywords(f"{title} {body}", keywords):
            continue
        space = p.get("space") or {}
        sid = space.get("id", "")
        url = p.get("link") or f"https://snapshot.org/#/{sid}/proposal/{p.get('id')}"
        items.append(
            Item(
                source=NAME,
                kind="lead",
                external_id=p["id"],
                title=title,
                org=space.get("name") or sid,
                url=url,
                description=clean_text(body),
                deadline=_iso(p.get("end")),
                posted_at=_iso(p.get("created")),
            )
        )
    return items


def fetch(cfg: dict | None = None) -> list[Item]:
    with client() as c:
        r = c.post(URL, json={"query": QUERY})
        r.raise_for_status()
        return parse(r.json(), (cfg or {}).get("lead_keywords"))
