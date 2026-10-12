"""Rule-based scam / red-flag detection. Flags are warnings; items are never dropped."""
from __future__ import annotations

import re

from .models import Item

PATTERNS: list[tuple[str, str]] = [
    (r"download (and|&) (run|install|execute)", "asks you to download and run something"),
    (r"clone (the|this|our) (repo|repository)[^.\n]{0,60}\brun\b", "asks you to clone a repo and run it"),
    (r"take[- ]?home[^.\n]{0,80}run (it )?locally", "take-home that must be run locally"),
    (r"run (it |the (code|project|app) )?locally", "asks you to run code locally"),
    (r"pay (a|an|the) (small |one[- ]time |registration |application )?fee", "asks you to pay a fee"),
    (r"\b(security |refundable |registration )?deposit\b", "mentions a deposit"),
    (r"purchase[^.\n]{0,40}starter ?kit", "asks you to purchase a starter kit"),
    (r"paid (in|with) (our|the project'?s?|company) (native )?token (only)?", "paid in own token only"),
    (r"(token|tokens) only", "paid in tokens only"),
    (r"\bdm (us |me )?(on|via) telegram to apply", "apply by Telegram DM"),
]
COMPILED = [(re.compile(p, re.I), msg) for p, msg in PATTERNS]
HUGE_PAY_USD = 20000
STABLE = {"", "USD", "USDC", "USDT", "DAI"}


def check(item: Item, huge_pay: float = HUGE_PAY_USD) -> list[str]:
    text = f"{item.title}\n{item.description}"
    flags: list[str] = []
    for rx, msg in COMPILED:
        if rx.search(text) and msg not in flags:
            flags.append(msg)
    if "apply by Telegram DM" in flags and item.org:
        flags.remove("apply by Telegram DM")  # only suspicious with no company
    if item.kind == "gig" and not item.org:
        top = max(item.pay_min or 0, item.pay_max or 0)
        if top >= huge_pay and item.pay_currency.upper() in STABLE:
            flags.append("no organisation but very high pay")
    return flags
