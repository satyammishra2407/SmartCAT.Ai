"""Validate required fields before RMS/AIR export."""
from __future__ import annotations

from typing import Any


def validate_locations(df_rows: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    required = ["Street", "City", "PostalCode", "Country", "Latitude", "Longitude"]
    missing_critical: list[str] = []
    if not df_rows:
        return False, ["No rows to export"]
    row0 = df_rows[0]
    for col in required:
        col_alt = col.lower().replace(" ", "")
        present = any(k.lower().replace(" ", "") == col_alt for k in row0.keys())
        if not present:
            missing_critical.append(f"Missing column hint: {col}")
    return len(missing_critical) == 0, missing_critical


def validate_slip_terms(terms: dict[str, Any]) -> tuple[bool, list[str]]:
    msgs: list[str] = []
    if not terms.get("limits_occurrence") and not terms.get("limits_aggregate"):
        msgs.append("Limits not found — confirm manually.")
    return len(msgs) == 0, msgs
