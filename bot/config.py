"""Config loading. Secrets come only from environment variables."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DB_PATH = ROOT / "data" / "leads.db"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
HTTP_TIMEOUT = 20.0


def _load(name: str) -> dict[str, Any]:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_profile() -> dict[str, Any]:
    return _load("profile.yaml")


def load_sources_config() -> dict[str, Any]:
    return _load("sources.yaml")


def load_watchlist() -> dict[str, Any]:
    return _load("watchlist.yaml")


def env(name: str) -> str | None:
    v = os.environ.get(name)
    return v or None
