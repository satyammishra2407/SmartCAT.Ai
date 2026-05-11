"""Detect address-related columns from SOV headers via keyword matching."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from smartcat_logging import get_logger

logger = get_logger("module1.columns")


def load_keywords(path: Path | None = None) -> dict[str, list[str]]:
    base = Path(__file__).resolve().parents[2] / "config" / "column_keywords.json"
    p = path or base
    with open(p, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return {k: [str(x).lower() for x in v] for k, v in data.items()}


def _normalize_header(h: str) -> str:
    return re.sub(r"\s+", " ", str(h).strip().lower())


def detect_columns(df_columns: list[str], keywords: dict[str, list[str]] | None = None) -> dict[str, str | None]:
    """
    Map semantic roles to the best-matching column name in the dataframe.
    Returns keys: street, city, state, postal_code, country, full_address (optional), etc.
    """
    kw = keywords or load_keywords()
    cols_norm = [(c, _normalize_header(c)) for c in df_columns]
    assigned: dict[str, str | None] = {role: None for role in kw}

    scored: list[tuple[int, str, str]] = []
    for role, terms in kw.items():
        best_score = 0
        best_col: str | None = None
        for orig, nc in cols_norm:
            for term in terms:
                if term == nc:
                    s = 100
                elif term in nc:
                    s = 80
                elif nc in term and len(term) <= len(nc) + 3:
                    s = 60
                else:
                    continue
                if s > best_score:
                    best_score = s
                    best_col = orig
        assigned[role] = best_col
        if best_col:
            scored.append((best_score, role, best_col))

    # If we have a strong single "address" column but no street, alias street from fullest match
    if assigned.get("street") is None:
        for orig, nc in cols_norm:
            if "address" in nc and "email" not in nc:
                assigned["street"] = orig
                logger.info("Using '%s' as street/full-address column", orig)
                break

    logger.info("Column detection: %s", assigned)
    return assigned


def build_full_address_row(row: dict, mapping: dict[str, str | None]) -> str | None:
    """Concatenate split columns into one line when no single full string exists."""
    parts: list[str] = []
    for key in ("street", "city", "state", "postal_code", "country"):
        col = mapping.get(key)
        if col and col in row and row[col] is not None:
            v = str(row[col]).strip()
            if v and v.lower() != "nan":
                parts.append(v)
    return ", ".join(parts) if parts else None
