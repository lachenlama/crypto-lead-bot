"""Public Telegram channel previews (https://t.me/s/{channel})."""
from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from ..http import client
from ..models import Item, clean_text

log = logging.getLogger(__name__)
NAME = "telegram_channels"


def parse(html_text: str, channel: str = "") -> list[Item]:
    try:
        soup = BeautifulSoup(html_text, "html.parser")
        items = []
        for msg in soup.select("div.tgme_widget_message"):
            post = msg.get("data-post")
            text_el = msg.select_one("div.tgme_widget_message_text")
            if not post or not text_el:
                continue
            text = text_el.get_text("\n", strip=True)
            if not text:
                continue
            t = msg.select_one("time[datetime]")
            title = text.split("\n", 1)[0][:140]
            items.append(
                Item(
                    source=f"telegram:{post.split('/')[0] or channel}",
                    kind="job",
                    external_id=post,
                    title=title,
                    url=f"https://t.me/{post}",
                    description=clean_text(text),
                    posted_at=t["datetime"] if t else "",
                )
            )
        return items
    except Exception as e:  # structure changed
        log.warning("telegram parse failed: %s", e)
        return []


def fetch(cfg: dict | None = None) -> list[Item]:
    channels = (cfg or {}).get("telegram_channels") or ["cryptojobslist"]
    items: list[Item] = []
    failed = 0
    with client() as c:
        for ch in channels:
            try:
                r = c.get(f"https://t.me/s/{ch}")
                r.raise_for_status()
                found = parse(r.text, ch)
                if not found:
                    log.warning("telegram channel %s: no messages parsed", ch)
                items.extend(found)
            except Exception as e:
                failed += 1
                log.warning("telegram channel %s failed: %s", ch, e)
    if failed and failed == len(channels):
        raise RuntimeError("all telegram channels failed")
    return items
