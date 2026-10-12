"""Telegram alerts via Bot API sendMessage (HTML). Falls back to stdout."""
from __future__ import annotations

import html
import logging
import os
import time

import httpx

from .models import Item

log = logging.getLogger(__name__)
LIMIT = 4096
SAFE = 3900  # headroom


def split_message(text: str, limit: int = LIMIT) -> list[str]:
    """Split on line boundaries; hard-split lines longer than the limit."""
    if len(text) <= limit:
        return [text]
    parts, cur = [], ""
    for line in text.split("\n"):
        while len(line) > limit:
            if cur:
                parts.append(cur)
                cur = ""
            parts.append(line[:limit])
            line = line[limit:]
        if len(cur) + len(line) + (1 if cur else 0) > limit:
            parts.append(cur)
            cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur:
        parts.append(cur)
    return parts


def fmt_pay(it: Item) -> str:
    if not it.has_pay:
        return "n/a"
    lo, hi = it.pay_min, it.pay_max
    rng = f"{lo:,.0f}" if lo == hi or hi is None else f"{lo or 0:,.0f}-{hi:,.0f}"
    return f"{rng} {it.pay_currency} /{it.pay_unit}".strip()


def format_alert(it: Item) -> str:
    e = html.escape
    lines = [f"<b>{e(it.title)}</b>"]
    lines.append(f"{e(it.org or 'unknown org')} | {e(it.kind)} | {e(it.source)}")
    lines.append(f"Pay: {e(fmt_pay(it))}" + (f" | Deadline: {e(it.deadline)}" if it.deadline else ""))
    lines.append(f"Score: <b>{it.score}</b> - {e(it.score_reason)}")
    if it.package:
        lines.append(f"Package: {e(it.package)}")
    if it.scam_flags:
        lines.append("⚠️ Warning: " + e("; ".join(it.scam_flags)))
    lines.append(e(it.url))
    base = "\n".join(lines)
    if it.pitch:
        room = SAFE - len(base) - 40
        pitch = html.escape(it.pitch)
        if len(pitch) > room > 0:
            pitch = pitch[: room - 1] + "…"
        if room > 0:
            base += f"\n<blockquote>{pitch}</blockquote>"
    return base


def format_digest(items: list[Item]) -> str:
    e = html.escape
    lines = [f"<b>Digest: {len(items)} more leads (score 50-69)</b>"]
    for it in items:
        warn = " ⚠️" if it.scam_flags else ""
        lines.append(f"{it.score} | <a href=\"{e(it.url, quote=True)}\">{e(it.title[:80])}</a> - {e(it.org or it.source)}{warn}")
    return "\n".join(lines)


class Notifier:
    def __init__(self, dry_run: bool = False, sleep: float = 1.0):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        self.dry_run = dry_run or not (self.token and self.chat_id)
        self.sleep = sleep
        self.sent = 0

    def send(self, text: str) -> bool:
        ok = True
        for part in split_message(text):
            if self.dry_run:
                print(part)
                print("-" * 40)
            else:
                ok = self._post(part) and ok
                time.sleep(self.sleep)
            self.sent += 1
        return ok

    def _post(self, text: str) -> bool:
        try:
            r = httpx.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=20,
            )
            if r.status_code != 200:
                log.warning("telegram send failed: HTTP %s", r.status_code)
                return False
            return True
        except Exception as e:  # never log the URL (contains the token)
            log.warning("telegram send error: %s", type(e).__name__)
            return False
