"""Pick RMS / Euro / JPBldg scheme from country column."""
from __future__ import annotations


def select_scheme(country: str | None) -> str:
    if not country:
        return "RMS"
    c = str(country).strip().upper()
    if c in ("JP", "JAPAN"):
        return "JPBldg"
    eu = {
        "DE",
        "FR",
        "ES",
        "IT",
        "NL",
        "BE",
        "PL",
        "SE",
        "NO",
        "FI",
        "DK",
        "AT",
        "CH",
        "IE",
        "PT",
        "GR",
        "EU",
    }
    if c in eu:
        return "EURO"
    return "RMS"
