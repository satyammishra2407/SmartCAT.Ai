# SmartCAT.AI — Slip Extraction Rules

Derived from **Slip Coding.pdf**, **Sample 2.pdf**, and **Sample 4.pdf**.

## Output structure

| Sheet / table | Purpose |
|---------------|---------|
| **Policy Summary** | One row per slip: TIV, dates, program limit, participation, SIR, blanket deductible |
| **Limits & Sublimits** | One row per limit line (program limit, peril sublimits, coverage extensions) |
| **Deductibles** | One row per deductible rule (per peril, region, coverage type) |
| **Waiting Periods** | Time-based deductibles (e.g. Service Interruption 24 hours) |
| **CAT Peril Summary** | Rolled-up view for EQ, WS, FL, AOP with limit + deductible |

Machine-readable schema: `config/slip_schema.json`.

---

## Policy summary fields

| Field | Where to find | Extraction rule |
|-------|---------------|-----------------|
| **TIV** | First pages, “TIV info”, “Sum Insured” | Parse currency; store notes (e.g. “48% International”) in `tiv_notes` |
| **Effective / Expiration** | Policy period block | MM/DD/YYYY; if exactly 365 days, expiry = day before (per Slip Coding) |
| **Limit of Liability / Program Limit** | “Limits of Liability”, “Policy condition” table row | Primary cap; Sample 2: $200M; Sample 4: $50M |
| **Blanket Limit** | Account-level RMS field `BLANLIMAMT` | Single limit for all locations combined |
| **Part Of / Participation** | Coinsurance section | “$300M part of $400M” → part_of + layer; store % in `participation_pct` |
| **Excess Of / SIR** | After policy limit, “Self-Insured Retention” | Map to `excess_of` / RMS `UNDCOVAMT` |
| **Blanket Deductible** | Deductible section default | RMS `BLANDEDAMT`; “all other losses” wording |
| **Min / Max Deductible** | % deductibles with floor/cap | RMS `MINDEDAMT`, `MAXDEDAMT` |

---

## Limits & sublimits — row rules

### Row types

1. **limit** — Program / limit of liability (top-level cap)
2. **sublimit** — Lower cap for peril, region, or occupancy
3. **coverage_extension** — Accounts Receivable, Debris Removal, etc.
4. **other** — Unclassified table rows

### Peril detection (RMS codes)

| RMS | Trigger keywords |
|-----|------------------|
| EQ | Earth Movement, Earthquake, Seismic |
| WS | Named Storm, Named Windstorm, Windstorm, Hurricane |
| FL | Flood, Sturmflut |
| FR / AOP | All Other Perils, Fire (non-CAT extensions) |
| SCS | Severe Convective Storm, Hail, Tornado |
| WF | Wildfire |

### Sublimit nesting (Sample 2 pattern)

```
Flood, per Occurrence and annual aggregate     →  $100,000,000  (parent)
  Flood - High Hazard Zones                    →  $15,000,000   (child, parent_peril=Flood)
  Flood - Moderate Hazard Zones                →  $30,000,000
```

**Rules (Slip Coding p.21):**

- If sublimit > policy limit + excess → do not capture
- Peril-wide or region-wide sublimits → blanket limit (`PARTOF`)
- Location-specific sublimits → flag for RiskLink Special Conditions
- Skip non-CAT items (boiler, fine art) unless 100% of location value

### Status values

- **included** — “Included” in limit column
- **excluded** — “Excluded”, “US$ Excluded” (Sample 4 CA EQ)
- **active** — Dollar amount present
- **n/a** — Not stated

### Basis

- **occurrence** — “per Occurrence”
- **annual_aggregate** / **policy_year** — “annual aggregate”, “any one Policy year”
- **aggregate** — General aggregate wording

---

## Deductibles — row rules

### Types (Slip Coding p.23)

| Type | Example | Fields |
|------|---------|--------|
| **monetary** | $1,000,000 per Occurrence | `amount` |
| **percent** | 5% of TIV / value per Location | `pct`, optional `min_amount`, `max_amount` |
| **hybrid** | 2% min $100K max $250K | all three |
| **waiting_period** | 24 Hours, 180 Days | → Waiting Periods sheet |
| **excluded** | California Earthquake: Excluded | `deductible_type=excluded` |

### Coverage types

- **combined** — “combined all coverages”, PD + TE together
- **property_damage** — PD, Building, CV1
- **time_element** — TE, BI, CV3
- **contents** — Contents, CV2

### Regional / hazard qualifiers

Extract from description text:

- High Hazard Zones (Wind, Flood, Earth Movement)
- California, New Madrid, Pacific Northwest, Japan, Mexico
- Special Flood Hazard Area (SFHA), Moderate Flood Hazard Area (MFHA)
- US Tier 1 Named Storm

### Application basis

- **per_occurrence** — “per Occurrence”, “any one loss”
- **per_location** — “per Location”
- **per_building** — SFHA building deductible
- **per_unit** — “per Unit of Insurance”

### Sample 2 deductibles (reference)

| Peril | Rule |
|-------|------|
| AOP | $1,000,000 combined all coverages, per Occurrence |
| Earth Movement (default) | $1,000,000 |
| Earth Movement — PNW/NM/AK/HI/PR/MX | 2% PD + 2% TE, min $1M |
| Earth Movement — CA/Japan/High Hazard | 5% PD + 5% TE, min $1M |
| Named Storm (default) | $1,000,000 |
| Named Storm — High Hazard Wind | 3% PD + 3% TE, min $1M |
| Flood | $1,000,000 |

### Sample 4 deductibles (reference)

| Peril | Rule |
|-------|------|
| AOP / Property Damage+TE Combined | $100,000 |
| Earthquake (default) | $100,000 |
| CA Earthquake | Excluded |
| New Madrid / PNW EQ | 2% TIV, min $100K / max $250K |
| Flood (default) | $100,000 |
| SFHA Flood | $500K PD / $500K contents / $100K TE |
| Named Storm Tier 1 | 5% TIV, min $100K / max $400K |
| Service Interruption | 24 Hours waiting period |
| Transit | $10,000 |

### Deductible application logic (Sample 2 p.4)

1. Multiple deductibles on one occurrence → apply separately; total deduction ≤ largest single deductible
2. TE not in occurrence calc if no TE claim; same for PD
3. Primary/government funding may reduce effective deductible

---

## Waiting periods

| Coverage | Sample value | Rule |
|----------|--------------|------|
| Service Interruption | 24 hours | No liability until period of recovery exceeds waiting period |
| Extended Period of Liability | 180 Days | Store in waiting_periods with `days=180` |

---

## Coinsurance / participation

- Expressed as % or “$X part of $Y xs $Z”
- For CAT modeling: assume **100% line** in `BLANLIMAMT` (Slip Coding p.18)
- Store actual participation in `participation_pct` for reference

---

## Supported inputs

| Format | Method |
|--------|--------|
| Text PDF | pdfplumber text + table extraction |
| Scanned PDF | PyMuPDF rasterize → Tesseract OCR (if installed) |
| Word (.docx) | python-docx paragraph + table read |
| Images (.png, .jpg, .jpeg, .tiff, .bmp) | Tesseract OCR |

---

## Confidence scoring

- +30 TIV found
- +20 program limit found
- +15 ≥3 limit/sublimit rows
- +15 ≥2 deductible rows
- +10 dates found
- +10 OCR not required

Max 100.

---

## Files

- Schema: `config/slip_schema.json`
- Patterns: `modules/module3_slip_extraction/pattern_library.py`
- Table parser: `modules/module3_slip_extraction/table_parser.py`
- Engine: `modules/module3_slip_extraction/pdf_processor.py` (`SlipExtractionEngine`)
