"""RemoteOK JSON API. Element 0 is a legal notice. Attribution link is kept."""
from __future__ import annotations

import re

from ..http import client
from ..models import Item, clean_text

NAME = "remoteok"
URL = "https://remoteok.com/api?tag=crypto"
ATTRIBUTION = "Source: RemoteOK (https://remoteok.com)"


CRYPTO_RE = re.compile(
    r"(?<![a-z0-9])(crypto|web3|blockchain|defi|on-?chain|ethereum|solana|tokens?|daos?|"
    r"stablecoins?|wallets?|nfts?|bitcoin)(?![a-z0-9])",
    re.I,
)


def is_crypto(row: dict) -> bool:
    """tag=crypto also returns unrelated jobs (tagged crypto anyway), so require a crypto term
    in the title or description; tags alone aren't trusted."""
    text = " ".join([row.get("position") or "", clean_text(row.get("description"))])
    return bool(CRYPTO_RE.search(text))


def _num(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def parse(data: list) -> list[Item]:
    items = []
    for row in data[1:]:  # skip legal notice
        if not isinstance(row, dict) or not row.get("position"):
            continue
        if not is_crypto(row):
            continue
        lo, hi = _num(row.get("salary_min")), _num(row.get("salary_max"))
        url = row.get("url") or row.get("apply_url") or ""
        desc = clean_text(row.get("description"), 1900) + f"\n{ATTRIBUTION}"
        items.append(
            Item(
                source=NAME,
                kind="job",
                external_id=str(row.get("id") or url),
                title=row["position"],
                org=row.get("company", "") or "",
                url=url,
                description=desc,
                pay_min=lo,
                pay_max=hi,
                pay_currency="USD" if (lo or hi) else "",
                pay_unit="year" if (lo or hi) else "unknown",
                posted_at=row.get("date", "") or "",
                tags=list(row.get("tags") or []),
            )
        )
    return items


def fetch(cfg: dict | None = None) -> list[Item]:
    with client() as c:
        r = c.get(URL)
        r.raise_for_status()
        return parse(r.json())
