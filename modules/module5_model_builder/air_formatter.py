"""AIR Touchstone-style CSV export (fixed column layout)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

AIR_COLUMNS = [
    "LocID",
    "Street",
    "City",
    "State",
    "Zip",
    "Country",
    "Lat",
    "Lon",
    "ConstCode",
    "OccCode",
    "TIV",
    "Deductible",
    "Limit",
]


def _series(df: pd.DataFrame, *names: str, default: str = "") -> pd.Series:
    for n in names:
        if n in df.columns:
            s = df[n]
            return s if isinstance(s, pd.Series) else pd.Series(s)
    return pd.Series([default] * len(df), index=df.index)


def _air_deductible_limit(slip: dict[str, Any] | None) -> tuple[str, str]:
    """Single Deductible / Limit column strings from consolidated slip (placeholders OK)."""
    if not slip:
        return "", ""
    lim_occ = slip.get("limits_occurrence") or slip.get("limit_occurrence") or ""
    lim_occ = str(lim_occ) if lim_occ is not None else ""
    deds = slip.get("deductibles")
    ded_str = ""
    if isinstance(deds, list) and deds:
        ded_str = "; ".join(str(x) for x in deds)
    elif deds:
        ded_str = str(deds)
    return ded_str, lim_occ


def write_air_csv(
    df: pd.DataFrame,
    out_path: Path,
    slip_terms: dict[str, Any] | None = None,
) -> Path:
    sub = df.copy()
    n = len(sub)

    seq = pd.Series(range(1, n + 1), index=sub.index)
    if "LocID" in sub.columns:
        loc = pd.to_numeric(sub["LocID"], errors="coerce").fillna(seq).astype(int)
    elif "LocationID" in sub.columns:
        loc = pd.to_numeric(sub["LocationID"], errors="coerce").fillna(seq).astype(int)
    else:
        loc = seq.astype(int)

    street = _series(sub, "Street", "StreetAddress", default="").astype(str).fillna("")
    city = _series(sub, "City", default="").astype(str).fillna("")
    state = _series(sub, "State", default="").astype(str).fillna("")
    zip_code = _series(sub, "PostalCode", "Zip", "ZIP", default="").astype(str).fillna("")
    country = _series(sub, "Country", default="").astype(str).fillna("")

    lat = pd.to_numeric(sub["Latitude"], errors="coerce") if "Latitude" in sub.columns else pd.Series([None] * n)
    lon = pd.to_numeric(sub["Longitude"], errors="coerce") if "Longitude" in sub.columns else pd.Series([None] * n)
    if not isinstance(lat, pd.Series):
        lat = pd.Series(lat)
    if not isinstance(lon, pd.Series):
        lon = pd.Series(lon)

    const_code = _series(sub, "MappedConstructionCode", "ConstCode", default="").astype(str).fillna("")
    occ_code = _series(sub, "MappedOccupancyCode", "OccCode", default="").astype(str).fillna("")

    tiv = pd.to_numeric(sub["TIV"], errors="coerce") if "TIV" in sub.columns else pd.Series([None] * n)
    if "BuildingTIV" in sub.columns:
        tiv = tiv.fillna(pd.to_numeric(sub["BuildingTIV"], errors="coerce"))
    tiv = tiv.fillna(0)

    ded, lim = _air_deductible_limit(slip_terms)
    ded_col = [ded] * n
    lim_col = [lim] * n

    out = pd.DataFrame(
        {
            "LocID": loc,
            "Street": street,
            "City": city,
            "State": state,
            "Zip": zip_code,
            "Country": country,
            "Lat": lat,
            "Lon": lon,
            "ConstCode": const_code,
            "OccCode": occ_code,
            "TIV": tiv,
            "Deductible": ded_col,
            "Limit": lim_col,
        },
        index=sub.index,
    )

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out[AIR_COLUMNS].to_csv(out_path, index=False)
    return out_path
