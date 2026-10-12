"""Pipeline entrypoint: python -m bot.main [--dry-run] [--source NAME] [--limit N]."""
from __future__ import annotations

import argparse
import logging
import sys

from . import db, pitch, scam, score
from .config import DB_PATH, load_profile, load_sources_config
from .models import Item
from .sources import SOURCES
from .telegram import Notifier, format_alert, format_digest

log = logging.getLogger("bot")


def fetch_all(names: list[str], cfg: dict, limit: int | None) -> tuple[list[tuple[str, Item]], dict]:
    items: list[tuple[str, Item]] = []
    stats: dict[str, dict] = {}
    for name in names:
        st = stats[name] = {"fetched": 0, "new": 0, "errors": 0}
        try:
            got = SOURCES[name].fetch(cfg)
            if limit:
                got = got[:limit]
            st["fetched"] = len(got)
            items.extend((name, it) for it in got)
        except Exception as e:
            st["errors"] += 1
            log.error("source %s failed: %s: %s", name, type(e).__name__, str(e)[:200])
    return items, stats


def run(args: argparse.Namespace) -> int:
    cfg = load_sources_config()
    profile = load_profile()
    th = cfg.get("thresholds", {})
    alert_min = int(th.get("alert", 70))
    digest_min = int(th.get("digest_min", 50))
    digest_size = int(th.get("digest_size", 10))
    max_instant = int(th.get("max_instant_alerts", 15))

    enabled = [n for n in SOURCES if cfg.get("enabled", {}).get(n, False)]
    if args.source:
        if args.source not in SOURCES:
            log.error("unknown source %s (known: %s)", args.source, ", ".join(SOURCES))
            return 2
        enabled = [args.source]

    # 1-2. fetch, dedupe
    fetched, stats = fetch_all(enabled, cfg, args.limit)
    conn = None
    if not args.dry_run or DB_PATH.exists():
        conn = db.connect(DB_PATH)
    seen = db.existing_keys(conn)
    new: list[Item] = []
    for name, it in fetched:
        if it.key in seen:
            continue
        seen.add(it.key)
        new.append(it)
        stats[name]["new"] += 1

    # 3. scam
    for it in new:
        it.scam_flags = scam.check(it, float(th.get("huge_pay_usd", scam.HUGE_PAY_USD)))
    # 4. score, 5. pitches
    score.score_items(new, profile, cfg)
    # only pitch the top items (the ones that can become instant alerts) to keep API cost bounded
    top = sorted(new, key=lambda i: i.score or 0, reverse=True)[:max_instant]
    pitch.draft_pitches(top, profile, cfg)

    # 6. alerts
    notifier = Notifier(dry_run=args.dry_run)
    new.sort(key=lambda i: i.score or 0, reverse=True)
    # cap instant alerts so a first run (empty db) doesn't flood the chat
    instant = [i for i in new if (i.score or 0) >= alert_min][:max_instant]
    mid = [i for i in new if digest_min <= (i.score or 0) < alert_min][:digest_size]
    alerted: list[Item] = []
    for it in instant:
        if notifier.send(format_alert(it)):
            alerted.append(it)
    if mid:
        if notifier.send(format_digest(mid)):
            alerted.extend(mid)

    # 7. persist
    if not args.dry_run and conn is not None:
        alerted_keys = {i.key for i in alerted} if not notifier.dry_run else set()
        for it in new:
            db.save_item(conn, it, alerted=it.key in alerted_keys)
        conn.commit()
    if conn is not None:
        conn.close()

    for name, st in stats.items():
        log.info("source=%s fetched=%d new=%d errors=%d", name, st["fetched"], st["new"], st["errors"])
    log.info("done: new=%d alerts=%d digest=%d", len(new), len(instant), len(mid))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="bot.main")
    p.add_argument("--dry-run", action="store_true", help="no Telegram, no DB writes")
    p.add_argument("--source", help="run only this source")
    p.add_argument("--limit", type=int, help="max items per source")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # httpx logs URLs
    try:
        return run(args)
    except Exception:
        log.exception("fatal error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
