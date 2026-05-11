"""Tests for address scrubbing."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules.module1_address_scrubbing.column_detector import detect_columns
from modules.module1_address_scrubbing.scrubbing_engine import AddressScrubbingEngine


def test_detect_columns_street_zip():
    m = detect_columns(["Risk Address", "ZIP Code", "CityName", "ST"])
    assert m["street"] == "Risk Address"
    assert m["postal_code"] == "ZIP Code"


def test_scrub_split_columns():
    df = pd.DataFrame(
        [
            {
                "StreetAddress": "7015 Gateway Blvd",
                "City": "Newark",
                "State": "CA",
                "PostalCode": "94560",
                "Country": "US",
            }
        ]
    )
    eng = AddressScrubbingEngine(translate_api_key=None)
    out = eng.scrub_dataframe(df)
    assert out.iloc[0]["City"] == "Newark"
    assert "94560" in str(out.iloc[0]["PostalCode"])


def test_sample_sov_exists():
    p = Path(__file__).parent / "test_sample_data" / "sample_sov.xlsx"
    assert p.exists()
