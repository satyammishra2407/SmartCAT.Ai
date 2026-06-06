"""Tests for module3 slip extraction."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules.module3_slip_extraction import SlipExtractionEngine
from modules.module3_slip_extraction.entity_extractor import extract_from_text
from modules.module3_slip_extraction.excel_exporter import records_to_frames, save_excel

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PDF = ROOT / "tests" / "test_sample_data" / "sample_slip.pdf"
SAMPLE_2 = ROOT / "Sample 2.pdf"
SAMPLE_4 = ROOT / "Sample 4.pdf"


SAMPLE_TEXT = """
Slip sample 2
TIV info:
Effective Date: 09/15/2025
Expiration Date: 09/15/2026
Total Insurable Value (TIV): $1,541,758,630 USD
N.B. 48% TIV is International (Mexico, Europe & South Africa)

Policy condition: Limits & Sublimits
Limit of Liability: $200,000,000
Earth Movement, per Occurrence and in the annual aggregate: $100,000,000
Earth Movement - California: $2,500,000
Flood, per Occurrence and in the annual aggregate: $100,000,000
Flood - High Hazard Zones: $15,000,000

Deductibles
$1,000,000 combined all coverages, per Occurrence
Earth Movement except: $1,000,000
Earth Movement - California: 5% of the value per Location, min $1,000,000
Named Storm except: $1,000,000
Flood: $1,000,000
Waiting period: 72 hours
Coinsurance / Participation: 15%
Self-Insured Retention (SIR): $250,000
"""


def test_extract_from_text_tiv_and_limits():
    rec = extract_from_text(SAMPLE_TEXT, source_file="test.txt", extraction_method="text")
    assert rec["tiv"] == "1541758630"
    assert rec["limit_of_liability"] == "200000000"
    assert rec["effective_date"] == "09/15/2025"
    assert len(rec["limits_sublimits"]) >= 3
    assert len(rec["deductibles"]) >= 2
    assert rec["coinsurance_pct"] == 15.0
    assert rec["sir"] == "250000"


def test_sample_slip_pdf():
    if not SAMPLE_PDF.exists():
        pytest.skip("Run scripts/generate_sample_data.py first")
    engine = SlipExtractionEngine()
    rec = engine.extract_file(SAMPLE_PDF)
    assert rec["tiv"] == "125000000"
    assert rec["limits_sublimits"]
    assert rec["deductibles"]
    assert rec["confidence_score"] >= 50


def test_excel_export_multi_sheet(tmp_path):
    rec = extract_from_text(SAMPLE_TEXT, source_file="test.txt")
    xlsx = tmp_path / "out.xlsx"
    save_excel([rec], xlsx)
    frames = records_to_frames([rec])
    assert "Policy Summary" in frames
    assert "Limits & Sublimits" in frames
    assert len(frames["Policy Summary"]) == 1


@pytest.mark.parametrize("path", [SAMPLE_2, SAMPLE_4])
def test_real_sample_pdfs(path: Path):
    if not path.exists():
        pytest.skip(f"{path.name} not found")
    engine = SlipExtractionEngine()
    rec = engine.extract_file(path)
    assert rec["source_file"] == path.name
    # Scanned PDFs may have sparse text without Tesseract; engine should still return structure
    assert "limits_sublimits" in rec
    assert "deductibles" in rec
    assert rec["confidence_score"] >= 0


def test_schema_file_exists():
    schema = ROOT / "config" / "slip_schema.json"
    assert schema.exists()
    data = json.loads(schema.read_text(encoding="utf-8"))
    assert "policy_summary_fields" in data
    assert "cat_perils" in data
