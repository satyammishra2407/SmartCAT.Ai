"""Tab-delimited RMS RiskLink-style LOCATION and ACCOUNT exports."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

RMS_LOCATION_COLUMNS = [
    "LocationID",
    "Address1",
    "Address2",
    "City",
    "State",
    "PostalCode",
    "Country",
    "Latitude",
    "Longitude",
    "ConstructionCode",
    "OccupancyCode",
    "TIV_Building",
    "TIV_Contents",
    "TIV_BI",
    "YearBuilt",
    "NumStories",
]

RMS_ACCOUNT_COLUMNS = [
    "AccountID",
    "LocationID",
    "PolicyNumber",
    "Limit_Occurrence",
    "Limit_Aggregate",
    "Deductible_EQ",
    "Deductible_Wind",
    "Deductible_Flood",
    "Participation",
]


def _series(df: pd.DataFrame, *names: str, default: str | float | int | None = "") -> pd.Series:
    for n in names:
        if n in df.columns:
            s = df[n]
            return s if isinstance(s, pd.Series) else pd.Series(s)
    return pd.Series([default] * len(df), index=df.index)


def _numeric_series(df: pd.DataFrame, *names: str, default: float | None = None) -> pd.Series:
    s = _series(df, *names, default=default)
    return pd.to_numeric(s, errors="coerce")


def build_rms_locations_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Build RMS LOCATION export with exact column order (placeholders where SOV lacks fields)."""
    sub = df.copy()
    n = len(sub)

    seq = pd.Series(range(1, n + 1), index=sub.index)
    if "LocationID" in sub.columns:
        loc_id = pd.to_numeric(sub["LocationID"], errors="coerce").fillna(seq).astype(int)
    elif "LocID" in sub.columns:
        loc_id = pd.to_numeric(sub["LocID"], errors="coerce").fillna(seq).astype(int)
    else:
        loc_id = seq.astype(int)

    street = _series(sub, "Street", "StreetAddress", default="").astype(str).fillna("")
    addr2 = _series(sub, "Address2", "AddressLine2", "Suite", default="").astype(str).fillna("")

    city = _series(sub, "City", default="").astype(str).fillna("")
    state = _series(sub, "State", default="").astype(str).fillna("")
    postal = _series(sub, "PostalCode", "Zip", "ZIP", default="").astype(str).fillna("")
    country = _series(sub, "Country", default="").astype(str).fillna("")

    lat = _numeric_series(sub, "Latitude", "Lat", default=None)
    lon = _numeric_series(sub, "Longitude", "Lon", "Long", default=None)

    const_code = _series(sub, "MappedConstructionCode", "ConstructionCode", default="").astype(str).fillna("")
    occ_code = _series(sub, "MappedOccupancyCode", "OccupancyCode", default="").astype(str).fillna("")

    tiv_bldg = _numeric_series(sub, "TIV", "BuildingTIV", "TIV_Building", default=None)
    tiv_bldg = tiv_bldg.fillna(0)

    tiv_contents = _numeric_series(sub, "TIV_Contents", "ContentsTIV", default=None).fillna("")
    tiv_bi = _numeric_series(sub, "TIV_BI", "BITIV", default=None).fillna("")

    year_built = _numeric_series(sub, "YearBuilt", "sec_year_built", "year_built", default=None)
    year_out = year_built.copy()
    year_out = year_out.where(year_out.notna(), "")

    num_stories = _numeric_series(sub, "NumStories", "Stories", "sec_stories", default=None)
    stories_out = num_stories.copy()
    stories_out = stories_out.where(num_stories.notna(), "")

    out = pd.DataFrame(
        {
            "LocationID": loc_id,
            "Address1": street,
            "Address2": addr2,
            "City": city,
            "State": state,
            "PostalCode": postal,
            "Country": country,
            "Latitude": lat,
            "Longitude": lon,
            "ConstructionCode": const_code,
            "OccupancyCode": occ_code,
            "TIV_Building": tiv_bldg,
            "TIV_Contents": tiv_contents,
            "TIV_BI": tiv_bi,
            "YearBuilt": year_out,
            "NumStories": stories_out,
        },
        index=sub.index,
    )

    return out[RMS_LOCATION_COLUMNS]


def write_rms_locations(df: pd.DataFrame, out_path: Path) -> tuple[Path, pd.DataFrame]:
    """Write tab-delimited RMS locations file; returns path and the frame written."""
    out = build_rms_locations_dataframe(df)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, sep="\t", index=False)
    return out_path, out


def _slip_participation(slip: dict[str, Any] | None) -> str:
    if not slip:
        return ""
    v = slip.get("coinsurance_pct")
    if v is None or v == "":
        return ""
    return str(v)


def _slip_limits(slip: dict[str, Any] | None) -> tuple[str, str]:
    if not slip:
        return "", ""
    lo = slip.get("limits_occurrence") or ""
    la = slip.get("limits_aggregate") or ""
    return str(lo) if lo is not None else "", str(la) if la is not None else ""


def _deduct_placeholder(slip: dict[str, Any] | None) -> tuple[str, str, str]:
    """EQ / Wind / Flood deductibles not split in slip extractor — placeholders for template."""
    if not slip:
        return "", "", ""
    deds = slip.get("deductibles")
    blob = ""
    if isinstance(deds, list) and deds:
        blob = "; ".join(str(x) for x in deds)
    elif deds:
        blob = str(deds)
    return blob, "", ""


def write_rms_accounts(
    slip: dict[str, Any] | None,
    rms_locations_df: pd.DataFrame,
    out_path: Path,
    account_id: str = "ACC1",
) -> Path:
    """One account row per LocationID (policy fields repeated — common for RiskLink stubs)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if rms_locations_df is None or rms_locations_df.empty:
        pd.DataFrame(columns=RMS_ACCOUNT_COLUMNS).to_csv(out_path, sep="\t", index=False)
        return out_path

    policy = ""
    if slip:
        policy = str(slip.get("policy_form") or slip.get("PolicyNumber") or "")

    lim_occ, lim_agg = _slip_limits(slip)
    ded_eq, ded_wind, ded_flood = _deduct_placeholder(slip)
    participation = _slip_participation(slip)

    rows: list[dict[str, Any]] = []
    for lid in rms_locations_df["LocationID"].tolist():
        rows.append(
            {
                "AccountID": account_id,
                "LocationID": lid,
                "PolicyNumber": policy[:120],
                "Limit_Occurrence": lim_occ,
                "Limit_Aggregate": lim_agg,
                "Deductible_EQ": ded_eq,
                "Deductible_Wind": ded_wind,
                "Deductible_Flood": ded_flood,
                "Participation": participation,
            }
        )

    pd.DataFrame(rows, columns=RMS_ACCOUNT_COLUMNS).to_csv(out_path, sep="\t", index=False)
    return out_path


# Back-compat alias (older callers)
def write_rms_accounts_stub(slip: dict, out_path: Path, account_id: str = "ACC1") -> Path:
    empty = pd.DataFrame(columns=RMS_LOCATION_COLUMNS)
    return write_rms_accounts(slip, empty, out_path, account_id=account_id)
