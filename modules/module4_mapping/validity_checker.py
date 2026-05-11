"""Flag incompatible construction vs region/peril heuristics."""
from __future__ import annotations

from typing import Any


def check_construction_region(building_scheme_code: str, country: str | None) -> list[str]:
    """Return warning strings (empty if OK)."""
    warnings: list[str] = []
    c = (country or "").upper()
    code = (building_scheme_code or "").upper()
    if c in ("JP", "JAPAN") and "WOOD" in code:
        warnings.append("Wood-heavy construction may be atypical for Japan earthquake portfolios — verify engineering.")
    return warnings


def summarize_warnings(row: dict[str, Any]) -> str:
    ws = row.get("mapping_warnings") or []
    return "; ".join(ws) if isinstance(ws, list) else str(ws)
