"""Devfolio hackathons with open applications (public JSON API; mostly India)."""
from __future__ import annotations

from ..events import iso_date, prize_from_text
from ..http import client
from ..models import Item

NAME = "devfolio"
URL = "https://api.devfolio.co/api/hackathons"
MAX_PAGES = 5


def parse(data: dict) -> list[Item]:
    items = []
    for h in (data or {}).get("result") or []:
        if not isinstance(h, dict) or not h.get("name") or h.get("private"):
            continue
        st = h.get("hackathon_setting") or {}
        sub = st.get("subdomain") or h.get("slug")
        if not sub:
            continue
        if h.get("is_online"):
            loc = "Online"
        else:
            loc = ", ".join(x for x in (h.get("city"), h.get("country")) if x) or "not stated"
            if st.get("is_hybrid"):
                loc += " | Online (hybrid)"
        text = h.get("desc") or ""
        amount, cur = prize_from_text(text)
        themes = [t.get("name", "") for t in h.get("themes") or [] if isinstance(t, dict)]
        desc = "\n".join([
            f"Location: {loc}",
            f"Themes: {', '.join(themes)}",
            f"Dates: {iso_date(h.get('starts_at'))} to {iso_date(h.get('ends_at'))}",
            (h.get("tagline") or "").strip(),
            text,
        ])
        items.append(Item(
            source=NAME,
            kind="hackathon",
            external_id=h.get("uuid") or sub,
            title=h["name"],
            org="Devfolio",
            url=st.get("external_apply_url") or f"https://{sub}.devfolio.co/",
            description=desc,
            pay_min=amount,
            pay_max=amount,
            pay_currency=cur,
            pay_unit="fixed" if amount else "unknown",
            deadline=iso_date(st.get("reg_ends_at")) or iso_date(h.get("starts_at")),
            posted_at=h.get("starts_at") or "",
            tags=[t for t in themes if t and t != "No Restrictions"],
        ))
    return items


def fetch(cfg: dict | None = None) -> list[Item]:
    out = []
    with client() as c:
        for page in range(1, MAX_PAGES + 1):
            r = c.get(URL, params={"filter": "application_open", "page": page})
            r.raise_for_status()
            data = r.json()
            out.extend(parse(data))
            if page >= int(data.get("pages") or 1):
                break
    return out
