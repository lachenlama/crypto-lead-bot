"""SQLite storage."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Item

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  key TEXT PRIMARY KEY,
  source TEXT, kind TEXT, external_id TEXT, title TEXT, org TEXT, url TEXT,
  description TEXT, pay_min REAL, pay_max REAL, pay_currency TEXT, pay_unit TEXT,
  deadline TEXT, posted_at TEXT, tags TEXT,
  first_seen TEXT, score INTEGER, score_reason TEXT, package TEXT, pitch TEXT,
  alerted_at TEXT, scam_flags TEXT
);
CREATE TABLE IF NOT EXISTS pay_observations (
  key TEXT, source TEXT, title TEXT, pay_min REAL, pay_max REAL,
  unit TEXT, currency TEXT, seen_at TEXT
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path | str) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(SCHEMA)
    return conn


def existing_keys(conn: sqlite3.Connection | None) -> set[str]:
    if conn is None:
        return set()
    return {r[0] for r in conn.execute("SELECT key FROM items")}


def save_item(conn: sqlite3.Connection, it: Item, alerted: bool = False) -> None:
    ts = now()
    conn.execute(
        """INSERT OR REPLACE INTO items
        (key, source, kind, external_id, title, org, url, description, pay_min, pay_max,
         pay_currency, pay_unit, deadline, posted_at, tags, first_seen, score,
         score_reason, package, pitch, alerted_at, scam_flags)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
          COALESCE((SELECT first_seen FROM items WHERE key=?), ?),?,?,?,?,?,?)""",
        (
            it.key, it.source, it.kind, it.external_id, it.title, it.org, it.url,
            it.description, it.pay_min, it.pay_max, it.pay_currency, it.pay_unit,
            it.deadline, it.posted_at, json.dumps(it.tags),
            it.key, ts,
            it.score, it.score_reason, it.package, it.pitch,
            ts if alerted else None, json.dumps(it.scam_flags),
        ),
    )
    if it.has_pay:
        conn.execute(
            "INSERT INTO pay_observations VALUES (?,?,?,?,?,?,?,?)",
            (it.key, it.source, it.title, it.pay_min, it.pay_max, it.pay_unit,
             it.pay_currency, ts),
        )


def mark_alerted(conn: sqlite3.Connection, keys: list[str]) -> None:
    conn.executemany(
        "UPDATE items SET alerted_at=? WHERE key=?", [(now(), k) for k in keys]
    )
