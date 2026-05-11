"""Tests for geocoding helpers (no live API)."""
from __future__ import annotations

import pandas as pd

from modules.module2_geocoding.confidence_scorer import score_for_level
from modules.module2_geocoding.distribution_logic import redistribute_tiv_by_postal
from modules.module2_geocoding.fallback_chain import ResolutionLevel


def test_confidence_scores_order():
    assert score_for_level(ResolutionLevel.BUILDING) > score_for_level(ResolutionLevel.CITY)


def test_tiv_distribution_same_zip():
    df = pd.DataFrame(
        {
            "PostalCode": ["77002", "77002", "77002"],
            "TIV": [100.0, 100.0, 100.0],
            "Latitude": [29.76, 29.77, None],
            "Longitude": [-95.37, -95.38, None],
            "Confidence Score": [80, 80, 0],
            "Resolution": ["POSTAL", "POSTAL", "FAILED"],
        }
    )
    df["geocode_failed"] = df["Latitude"].isna()
    out = redistribute_tiv_by_postal(df, failed_mask_col="geocode_failed")
    assert out["Latitude"].notna().all()
