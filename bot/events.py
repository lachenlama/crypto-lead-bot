"""Helpers for hackathon / grant items: prize parsing, rough USD conversion, deadline parsing."""
from __future__ import annotations

import re
from datetime import date, datetime

EVENT_KINDS = ("hackathon", "grant")

# rough, for ranking only (never shown as a converted amount)
USD_RATE = {"USD": 1.0, "USDC": 1.0, "USDT": 1.0, "USDG": 1.0, "PYUSD": 1.0, "DAI": 1.0,
            "EUR": 1.08, "GBP": 1.27, "CAD": 0.72, "AUD": 0.65, "INR": 0.012, "SGD": 0.74}
SYMBOLS = [("$CAD", "CAD"), ("CA$", "CAD"), ("A$", "AUD"), ("S$", "SGD"), ("US$", "USD"),
           ("₹", "INR"), ("€", "EUR"), ("£", "GBP"), ("$", "USD"), ("Rs.", "INR"), ("Rs", "INR"), ("INR", "INR"),
           ("USD", "USD"), ("USDC", "USDC")]
AMOUNT = r"(\d{1,3}(?:,\d{2,3})+|\d+(?:\.\d+)?)\s*(k|K|lakh|lakhs|L)?"
_SYM_RE = "|".join(re.escape(s) for s, _ in sorted(SYMBOLS, key=lambda x: -len(x[0])))
MONEY_RE = re.compile(r"(?<![A-Za-z])(" + _SYM_RE + r")\s*" + AMOUNT)
POOL_RE = re.compile(r"prize|pool|bount|reward|win|cash", re.I)


def _amount(num: str, mult: str | None) -> float:
    v = float(num.replace(",", ""))
    if mult in ("k", "K"):
        v *= 1000
    elif mult and mult.lower().startswith("l"):
        v *= 100000
    return v


def parse_money(text: str) -> tuple[float | None, str]:
    """First money amount in text, e.g. '₹ 200,000' -> (200000.0, 'INR'). HTML must be stripped first."""
    m = MONEY_RE.search(text or "")
    if not m:
        return None, ""
    cur = dict(SYMBOLS)[m.group(1)]
    return _amount(m.group(2), m.group(3)), cur


def prize_from_text(text: str) -> tuple[float | None, str]:
    """Largest money amount mentioned near a prize/pool/bounty word in free text (descriptions)."""
    best: tuple[float, str] | None = None
    for m in MONEY_RE.finditer(text or ""):
        ctx = text[max(0, m.start() - 80): m.end() + 80]
        if not POOL_RE.search(ctx):
            continue
        amt, cur = _amount(m.group(2), m.group(3)), dict(SYMBOLS)[m.group(1)]
        if best is None or to_usd(amt, cur) > to_usd(*best):
            best = (amt, cur)
    return best if best else (None, "")


def to_usd(amount: float | None, currency: str) -> float | None:
    if amount is None:
        return None
    rate = USD_RATE.get((currency or "USD").upper())
    return amount * rate if rate else None


MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
DATE_RE = re.compile(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})")


def _mk(mon: str, day: str, year: str) -> date | None:
    m = MONTHS.get(mon[:3].lower())
    try:
        return date(int(year), m, int(day)) if m else None
    except ValueError:
        return None


def end_date(text: str) -> str:
    """End date of a range as ISO 'YYYY-MM-DD', or '' if unparseable.
    'Oct 17 - Nov 10, 2026' / 'Nov 13 - 20, 2026' / 'Jul 16, 2026 - Jan 15, 2027' / 'Sep 4th – Sep 16th, 2026'."""
    text = (text or "").strip()
    if not text:
        return ""
    parts = re.split(r"\s+[-–—]\s+", text)
    right, left = parts[-1], parts[0]
    d = DATE_RE.search(right)
    if d:
        out = _mk(*d.groups())
        return out.isoformat() if out else ""
    m = re.match(r"(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", right)  # 'Nov 13 - 20, 2026'
    mon = re.match(r"([A-Za-z]{3,9})", left)
    if m and mon:
        out = _mk(mon.group(1), m.group(1), m.group(2))
        return out.isoformat() if out else ""
    return ""


def iso_date(ts: str | None) -> str:
    """'2026-11-10T11:00:00.000Z' -> '2026-11-10'."""
    if not ts:
        return ""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return ""


def days_left(deadline: str, today: date | None = None) -> int | None:
    try:
        d = date.fromisoformat((deadline or "")[:10])
    except ValueError:
        return None
    return (d - (today or date.today())).days
