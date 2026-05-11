"""Map secondary characteristics from SOV columns when present."""
from __future__ import annotations

import re
from typing import Any

_KEYWORDS = {
    "roof_cover": ["roof", "roof cover", "roofing"],
    "roof_geom": ["roof geom", "roof shape", "roof geometry"],
    "opening_protection": ["opening", "window protection", "shutter"],
    "year_built": ["year built", "year constructed", "built"],
    "stories": ["stories", "floors", "number of stories", "# stories"],
}


def detect_secondary_columns(columns: list[str]) -> dict[str, str | None]:
    cols_lower = {c: str(c).lower() for c in columns}
    found: dict[str, str | None] = {k: None for k in _KEYWORDS}
    for sem, terms in _KEYWORDS.items():
        for orig, lc in cols_lower.items():
            for t in terms:
                if t in lc:
                    found[sem] = orig
                    break
            if found[sem]:
                break
    return found


def extract_secondaries(row: dict[str, Any], mapping: dict[str, str | None]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for sem, col in mapping.items():
        if col and col in row and row[col] is not None:
            val = row[col]
            if sem == "year_built":
                m = re.search(r"(19|20)\d{2}", str(val))
                out[sem] = int(m.group(0)) if m else val
            elif sem == "stories":
                m = re.search(r"\d+", str(val))
                out[sem] = int(m.group(0)) if m else val
            else:
                out[sem] = str(val).strip()
    return out
