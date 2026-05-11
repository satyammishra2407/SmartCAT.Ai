"""Generate tests/test_sample_data fixtures (SOV xlsx, slip PDF, model output CSV)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "test_sample_data"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    sov_rows = []
    samples = [
        ("7015 Gateway Blvd", "Newark", "CA", "94560", "US", "Office Building", "Concrete", 12_500_000),
        ("350 Fifth Ave", "New York", "NY", "10118", "US", "Office Building", "Steel", 45_000_000),
        ("233 S Wacker Dr", "Chicago", "IL", "60606", "US", "Retail", "Masonry", 8_000_000),
        ("1600 Amphitheatre Pkwy", "Mountain View", "CA", "94043", "US", "School", "Wood Frame", 22_000_000),
        ("〒160-0022 東京都新宿区新宿5丁目", "", "", "", "JP", "Hotel", "Japan RC", 15_000_000),
    ]
    for i, (st, city, stt, zipc, country, occ, cons, tiv) in enumerate(samples, start=1):
        sov_rows.append(
            {
                "LocID": i,
                "StreetAddress": st,
                "City": city,
                "State": stt,
                "PostalCode": zipc,
                "Country": country,
                "OccupancyDescr": occ,
                "ConstructionDescr": cons,
                "TIV": tiv,
            }
        )
    for i in range(8):
        sov_rows.append(
            {
                "LocID": len(sov_rows) + 1,
                "StreetAddress": f"{100 + i} Main St",
                "City": "Houston",
                "State": "TX",
                "PostalCode": "77002",
                "Country": "US",
                "OccupancyDescr": "Warehouse",
                "ConstructionDescr": "Steel",
                "TIV": 5_000_000 + i * 100_000,
            }
        )

    pd.DataFrame(sov_rows).to_excel(OUT / "sample_sov.xlsx", index=False)

    pdf_path = OUT / "sample_slip.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    w, h = letter
    y = h - 72
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y, "Sample Property Insurance Slip — DEMO ONLY")
    y -= 24
    c.setFont("Helvetica", 10)
    lines = [
        "Total Insurable Value (TIV): $125,000,000 USD",
        "Limits of Liability — Occurrence: $50,000,000",
        "Annual Aggregate Limit: $75,000,000",
        "Earthquake - California: Excluded",
        "Flood - High Hazard Zones: $15,000,000 sublimit",
        "Named Storm sublimit: $25,000,000",
        "Deductible: 5% of TIV, min $100,000, max $250,000",
        "Coinsurance / Participation: 15%",
        "Self-Insured Retention (SIR): $250,000",
        "Waiting period: 72 hours",
        "Policy form: All Risk Difference in Conditions (DIC)",
    ]
    for line in lines:
        c.drawString(72, y, line)
        y -= 14
    c.save()

    # Synthetic EP curve (OEP / AEP columns)
    rp = [10, 25, 50, 100, 250, 500, 1000]
    oep = [1.2e6 * (r / 10) ** 0.35 for r in rp]
    aep = [1.1 * x for x in oep]
    pd.DataFrame({"RP": rp, "OEP": oep, "AEP": aep}).to_csv(OUT / "sample_model_output.csv", index=False)

    print("Wrote:", OUT)


if __name__ == "__main__":
    main()
