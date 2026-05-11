"""Distribute failed-location TIV across geocoded peers in the same postal bucket."""
from __future__ import annotations

import pandas as pd

from smartcat_logging import get_logger

logger = get_logger("module2.distribution")


def redistribute_tiv_by_postal(
    df: pd.DataFrame,
    postal_col: str = "PostalCode",
    tiv_col: str = "TIV",
    lat_col: str = "Latitude",
    lon_col: str = "Longitude",
    failed_mask_col: str | None = None,
) -> pd.DataFrame:
    """
    For rows missing coordinates, assign centroid of lat/lon of rows with same postal code
    and proportionally add failed rows' TIV to successful rows (exposure weighting).
    """
    out = df.copy()
    if tiv_col not in out.columns:
        out[tiv_col] = 1.0

    def _num(s: pd.Series) -> pd.Series:
        return pd.to_numeric(s, errors="coerce").fillna(0.0)

    out[tiv_col] = _num(out[tiv_col])

    has_geo = out[lat_col].notna() & out[lon_col].notna()
    if failed_mask_col and failed_mask_col in out.columns:
        failed = out[failed_mask_col].astype(bool)
    else:
        failed = ~has_geo

    for postal, grp in out.groupby(postal_col):
        if pd.isna(postal) or str(postal).strip() == "":
            continue
        idx = grp.index
        ok_mask = has_geo.reindex(idx).fillna(False).to_numpy(dtype=bool)
        bad_mask = failed.reindex(idx).fillna(False).to_numpy(dtype=bool)
        ok_idx = idx[ok_mask]
        bad_idx = idx[bad_mask]
        ok = grp.loc[ok_idx]
        bad = grp.loc[bad_idx]
        if ok.empty or bad.empty:
            continue
        sum_tiv_ok = float(ok[tiv_col].sum())
        sum_tiv_bad = float(bad[tiv_col].sum())
        if sum_tiv_ok <= 0:
            logger.warning("Cannot distribute TIV for postal %s — no positive TIV on geocoded rows", postal)
            continue
        lat_c = float(ok[lat_col].astype(float).mean())
        lon_c = float(ok[lon_col].astype(float).mean())
        share = sum_tiv_bad / sum_tiv_ok
        idx_ok = ok.index
        out.loc[idx_ok, tiv_col] = out.loc[idx_ok, tiv_col] * (1 + share)
        idx_bad = bad.index
        out.loc[idx_bad, lat_col] = lat_c
        out.loc[idx_bad, lon_col] = lon_c
        out.loc[idx_bad, "Resolution"] = "DISTRIBUTED_POSTAL"
        conf_bad = pd.to_numeric(out.loc[idx_bad, "Confidence Score"], errors="coerce").fillna(35)
        out.loc[idx_bad, "Confidence Score"] = conf_bad.clip(upper=35)
        logger.info(
            "Distributed TIV %.2f across %s rows in postal %s",
            sum_tiv_bad,
            len(ok),
            postal,
        )

    return out


def attach_centroid_by_city(
    df: pd.DataFrame,
    city_col: str = "City",
    state_col: str = "State",
    lat_col: str = "Latitude",
    lon_col: str = "Longitude",
) -> pd.DataFrame:
    """Placeholder city centroids — extend with a gazetteer file for production."""
    centroids: dict[tuple[str, str], tuple[float, float]] = {
        ("newark", "ca"): (37.5297, -122.0402),
        ("new york", "ny"): (40.7128, -74.0060),
        ("chicago", "il"): (41.8781, -87.6298),
        ("houston", "tx"): (29.7604, -95.3698),
        ("san francisco", "ca"): (37.7749, -122.4194),
        ("shinjuku", "tokyo"): (35.6938, 139.7034),
    }
    out = df.copy()
    for i in out.index:
        if pd.notna(out.loc[i, lat_col]) and pd.notna(out.loc[i, lon_col]):
            continue
        c = str(out.loc[i, city_col]).strip().lower() if city_col in out.columns else ""
        s = str(out.loc[i, state_col]).strip().lower() if state_col in out.columns else ""
        key = (c, s)
        if key in centroids:
            lat, lon = centroids[key]
            out.loc[i, lat_col] = lat
            out.loc[i, lon_col] = lon
            out.loc[i, "Resolution"] = "CITY_CENTROID_STUB"
    return out
