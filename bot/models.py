"""Item dataclass shared by all sources."""
from __future__ import annotations

import hashlib
import html
import re
from dataclasses import asdict, dataclass, field
from typing import Any

MAX_DESC = 2000


def clean_text(s: str | None, limit: int = MAX_DESC) -> str:
    """Strip HTML tags/entities, collapse whitespace, truncate."""
    if not s:
        return ""
    s = html.unescape(s)
    s = re.sub(r"<(br|/p|/div|/li)\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\s*\n\s*", "\n", s).strip()
    return s[:limit]


@dataclass
class Item:
    source: str
    kind: str  # job | gig | lead
    external_id: str
    title: str
    org: str = ""
    url: str = ""
    description: str = ""
    pay_min: float | None = None
    pay_max: float | None = None
    pay_currency: str = ""
    pay_unit: str = "unknown"  # year | hour | fixed | unknown
    deadline: str = ""
    posted_at: str = ""
    tags: list[str] = field(default_factory=list)
    # Filled by the pipeline:
    score: int | None = None
    score_reason: str = ""
    package: str | None = None
    pitch: str = ""
    scam_flags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.description = (self.description or "")[:MAX_DESC]

    @property
    def key(self) -> str:
        return hashlib.sha1(
            (self.source + (self.external_id or self.url)).encode("utf-8")
        ).hexdigest()

    @property
    def has_pay(self) -> bool:
        return self.pay_min is not None or self.pay_max is not None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
