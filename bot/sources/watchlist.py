"""Target-company watchlist: public Greenhouse / Lever / Ashby job boards (no auth)."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import httpx

from ..config import load_watchlist
from ..http import client
from ..models import Item, clean_text

NAME = "watchlist"
log = logging.getLogger(__name__)

URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true",
    "lever": "https://api.lever.co/v0/postings/{token}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true",
}


def _iso_ms(ms) -> str:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def _tags(company: dict) -> list[str]:
    tags = ["target", f"tier{company.get('tier', 2)}"]
    if company.get("category") == "ai_eval":
        tags.append("ai_eval")
    return tags


def _item(company: dict, ext_id, title, url, location, posted, desc) -> Item:
    desc = clean_text(desc, 1900)
    if location:
        desc = f"Location: {location}\n{desc}"
    return Item(
        source=NAME,
        kind="job",
        external_id=f"{company['token']}:{ext_id}",
        title=clean_text(title, 300),
        org=company["name"],
        url=url or "",
        description=desc,
        posted_at=posted or "",
        tags=_tags(company),
    )


def parse_greenhouse(data: dict, company: dict) -> list[Item]:
    return [
        _item(company, j.get("id"), j["title"], j.get("absolute_url"),
              (j.get("location") or {}).get("name"), j.get("updated_at"), j.get("content"))
        for j in data.get("jobs", []) if j.get("title")
    ]


def parse_lever(data: list, company: dict) -> list[Item]:
    items = []
    for j in data:
        if not isinstance(j, dict) or not j.get("text"):
            continue
        cat = j.get("categories") or {}
        loc = ", ".join(x for x in (cat.get("location"), cat.get("team")) if x)
        items.append(_item(company, j.get("id"), j["text"], j.get("hostedUrl"), loc,
                           _iso_ms(j.get("createdAt")), j.get("descriptionPlain")))
    return items


def parse_ashby(data: dict, company: dict) -> list[Item]:
    items = []
    for j in data.get("jobs", []):
        if not j.get("title"):
            continue
        loc = j.get("location") or ""
        if j.get("isRemote"):
            loc = f"{loc} (remote)".strip()
        desc = j.get("descriptionPlain") or ""
        comp = (j.get("compensation") or {}).get("compensationTierSummary")
        if comp:
            desc = f"Compensation: {comp}\n{desc}"
        items.append(_item(company, j.get("id"), j["title"], j.get("jobUrl"), loc,
                           j.get("publishedAt"), desc))
    return items


PARSERS = {"greenhouse": parse_greenhouse, "lever": parse_lever, "ashby": parse_ashby}


def _words_re(words: list[str]) -> re.Pattern | None:
    if not words:
        return None
    alt = "|".join(re.escape(w.lower()).replace(r"\ ", " ") for w in words)
    return re.compile(r"(?<![a-z0-9])(?:" + alt + r")s?(?![a-z0-9])")


def title_ok(title: str, company: dict, wl: dict) -> bool:
    """Keep a title only if it has a role keyword and no exclude keyword."""
    t = re.sub(r"[-/_,()]", " ", title.lower())
    include = list(wl.get("role_keywords", []))
    if company.get("category") == "ai_eval":
        include += wl.get("ai_eval_role_keywords", [])
    inc, exc = _words_re(include), _words_re(wl.get("exclude_keywords", []))
    if exc and exc.search(t):
        return False
    return bool(inc and inc.search(t))


def fetch_company(c: httpx.Client, company: dict) -> list[Item]:
    """Raw (unfiltered) items for one company. Raises on HTTP / parse errors."""
    r = c.get(URLS[company["ats"]].format(token=company["token"]))
    r.raise_for_status()
    return PARSERS[company["ats"]](r.json(), company)


def _status(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        return str(e.response.status_code)
    return type(e).__name__


def fetch(cfg: dict | None = None) -> list[Item]:
    wl = load_watchlist()
    companies = wl.get("companies", [])
    items: list[Item] = []
    failed = 0
    with client() as c:
        for co in companies:
            try:
                got = fetch_company(c, co)
            except Exception as e:
                failed += 1
                log.warning("watchlist company=%s ats=%s status=%s", co.get("name"), co.get("ats"), _status(e))
                continue
            kept = [it for it in got if title_ok(it.title, co, wl)]
            if co.get("category") == "ai_eval":
                # staff roles at eval vendors (e.g. "Research Scientist") are ordinary target jobs;
                # only eval-type titles (rater, annotator, expert contributor...) count as AI eval gigs
                ev = _words_re(wl.get("ai_eval_role_keywords", []))
                for it in kept:
                    if not (ev and ev.search(re.sub(r"[-/_,()]", " ", it.title.lower()))):
                        it.tags.remove("ai_eval")
            items.extend(kept)
    if companies and failed == len(companies):
        raise RuntimeError("watchlist: all companies failed")
    return items


def check() -> list[tuple[str, str, str, str, int | None]]:
    """Hit every endpoint; return (name, ats, token, status, job count)."""
    rows = []
    with client() as c:
        for co in load_watchlist().get("companies", []):
            try:
                rows.append((co["name"], co["ats"], co["token"], "200", len(fetch_company(c, co))))
            except Exception as e:
                rows.append((co["name"], co["ats"], co["token"], _status(e), None))
    return rows
