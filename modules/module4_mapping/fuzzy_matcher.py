"""Fuzzy match free-text to mapping tables."""
from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz, process

from smartcat_logging import get_logger

logger = get_logger("module4.fuzzy")


def best_match(
    query: str,
    choices: list[tuple[str, dict[str, Any]]],
    score_cutoff: int = 72,
) -> tuple[dict[str, Any], int] | tuple[None, int]:
    """
    choices: list of (label, payload dict)
    Returns (payload, score 0-100) or (None, 0).
    """
    if not query or not choices:
        return None, 0
    labels = [c[0] for c in choices]
    hit = process.extractOne(query, labels, scorer=fuzz.token_sort_ratio)
    if hit is None:
        return None, 0
    _label, score, idx = hit
    if score < score_cutoff:
        return None, int(score)
    payload = choices[idx][1]
    logger.debug("Matched '%s' -> '%s' (%s)", query, labels[idx], score)
    return payload, int(score)
