"""Postal validation and simple ZIP→city hints (US)."""
from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path

from smartcat_logging import get_logger

logger = get_logger("module1.validator")


@lru_cache(maxsize=1)
def _postal_patterns(path: Path | None = None) -> list[tuple[str, str, str]]:
    base = Path(__file__).resolve().parents[2] / "config" / "country_postal_codes.csv"
    p = path or base
    rows: list[tuple[str, str, str]] = []
    with open(p, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append((row["country_iso2"], row["pattern"], row.get("zip_lookup_available", "")))
    return rows


def normalize_postal_display(postal: str | float | None) -> str:
    """Coerce Excel float ZIPs like 94560.0 back to plain digits."""
    if postal is None:
        return ""
    if isinstance(postal, float):
        if postal != postal:  # NaN
            return ""
        if postal == int(postal):
            postal = int(postal)
    s = str(postal).strip()
    if s.lower() in ("nan", "none"):
        return ""
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    return s


def validate_postal(postal: str, country_iso2: str) -> bool:
    cc = (country_iso2 or "US").upper()
    postal = normalize_postal_display(postal)
    for iso, pattern, _ in _postal_patterns():
        if iso == cc:
            try:
                return bool(re.match(pattern, postal, re.IGNORECASE))
            except re.error:
                logger.warning("Bad regex in country_postal_codes for %s", iso)
                return True
    return True


def suggest_city_from_zip(us_zip: str) -> str | None:
    """
    Minimal embedded US ZIP→city mapping for common codes (demo / offline fallback).
    Production deployments typically use a full ZCTA database.
    """
    z = re.sub(r"\D", "", str(us_zip))[:5]
    hints = {
        "94560": "Newark",
        "10001": "New York",
        "60601": "Chicago",
        "77002": "Houston",
        "94102": "San Francisco",
    }
    return hints.get(z)
