"""Pitch drafting step (skipped without an LLM key)."""
from __future__ import annotations

import logging

from . import llm
from .models import Item

log = logging.getLogger(__name__)


def needs_pitch(item: Item, threshold: int) -> bool:
    return (item.score or 0) >= threshold


def draft_pitches(items: list[Item], profile: dict, cfg: dict | None = None) -> None:
    if not llm.available():
        return
    cfg = cfg or {}
    threshold = int(cfg.get("thresholds", {}).get("pitch", 70))
    model = llm.model_for("pitch", cfg)
    for it in items:
        if not needs_pitch(it, threshold):
            continue
        try:
            it.pitch = llm.draft_pitch(it, profile, model)
        except Exception as e:
            log.warning("pitch failed for %s: %s", it.title[:40], type(e).__name__)
