"""ETHGlobal upcoming hackathons (parsed from the public events page; no API).
Only the "Upcoming" section is read, and conferences / meetups / co-working days are skipped."""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from ..events import end_date
from ..http import client
from ..models import Item

log = logging.getLogger(__name__)
NAME = "ethglobal"
URL = "https://ethglobal.com/events"
NOT_PLACE = re.compile(
    r"\d|^[–—-]$|hackathon|apply|^(mon|tue|wed|thu|fri|sat|sun)$|"
    r"^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*$", re.I)
NOT_HACKATHON =re.compile(r"\b(conference|meetup|co-?working|happy hour|summit|brunch|demo day)\b", re.I)


def parse(html: str) -> list[Item]:
    soup = BeautifulSoup(html or "", "html.parser")
    head = next((h for h in soup.find_all("h2") if h.get_text(" ", strip=True).startswith("Upcoming")), None)
    if head is None:
        log.warning("ethglobal: no Upcoming section found (page layout changed?)")
        return []
    items, seen = [], set()
    for a in head.parent.select('a[href^="/events/"]'):
        slug = a["href"].rstrip("/").rsplit("/", 1)[-1]
        if slug in seen:
            continue
        seen.add(slug)
        parts = [p for p in a.stripped_strings if p not in (",", "|")]
        text = " | ".join(parts)
        h = a.find(["h3", "h2"])
        title = h.get_text(" ", strip=True) if h else ""
        if not title:
            continue
        online = "Online" in parts
        if NOT_HACKATHON.search(text) or not (online or re.search(r"hackathon", text, re.I)):
            continue
        if online:
            loc = "Online"
        else:  # the place is what's left after the title once dates / labels are dropped: "Mumbai", "India"
            i = parts.index(title) if title in parts else -1
            place = [p for p in parts[i + 1:] if not NOT_PLACE.search(p)]
            loc = ", ".join(place[-2:]) or "not stated"  # taglines come first, the place last
        items.append(Item(
            source=NAME,
            kind="hackathon",
            external_id=slug,
            title=title,
            org="ETHGlobal",
            url=f"https://ethglobal.com/events/{slug}",
            description=f"Location: {loc}\nThemes: Ethereum\n{text}",
            deadline=end_date(text.replace(" | ", " ")),
            tags=["ethereum"],
        ))
    return items


def fetch(cfg: dict | None = None) -> list[Item]:
    with client() as c:
        r = c.get(URL)
        r.raise_for_status()
        return parse(r.text)
