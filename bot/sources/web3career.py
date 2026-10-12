"""Optional web3.career API (disabled by default; needs WEB3_CAREER_TOKEN)."""
from __future__ import annotations

import os

from ..http import client
from ..models import Item, clean_text

NAME = "web3career"
URL = "https://web3.career/api/v1"


def parse(data) -> list[Item]:
    rows = data[-1] if isinstance(data, list) and data and isinstance(data[-1], list) else data
    items = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict) or not r.get("title"):
            continue
        items.append(
            Item(
                source=NAME, kind="job",
                external_id=str(r.get("id") or r.get("apply_url", "")),
                title=r["title"], org=r.get("company", "") or "",
                url=r.get("apply_url", "") or "",
                description=clean_text(r.get("description")),
                posted_at=str(r.get("date", "") or ""),
                tags=list(r.get("tags") or []),
            )
        )
    return items


def fetch(cfg: dict | None = None) -> list[Item]:
    token = os.environ.get("WEB3_CAREER_TOKEN")
    if not token:
        raise RuntimeError("WEB3_CAREER_TOKEN not set")
    with client() as c:
        r = c.get(URL, params={"token": token, "remote": "true", "limit": 100})
        r.raise_for_status()
        return parse(r.json())
