# SmartCAT.AI

SmartCAT.AI is an end-to-end automation toolkit for catastrophe modeling workflows used by risk analysts and CAT modelers. It standardizes SOV addresses, geocodes exposures with auditable fallbacks, extracts insurance slip terms from PDFs, maps occupancy and construction codes, builds RMS/AIR import stubs, and generates interpretive charts and reports from vendor outputs.

## Requirements

- **Python 3.10+**
- Windows, macOS, or Linux
- Optional system packages: **Tesseract OCR**, **Poppler** (for scanned PDF rasterization), **libpostal** (optional; this project defaults to `usaddress` plus heuristics)

## Quick start

```bash
cd SmartCAT.Ai
python -m venv .venv
```

**Windows (PowerShell):**

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**macOS / Linux:**

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add API keys as needed:

```bash
cp .env.example .env
```

Generate bundled sample data (SOV, slip PDF, model CSV):

```bash
python scripts/generate_sample_data.py
```

### Run the GUI (Streamlit)

```bash
streamlit run app.py
```

### Run the CLI / pipeline

```bash
python cli.py --sov tests/test_sample_data/sample_sov.xlsx --module1 --module4
```

Example with geocoding (requires `GOOGLE_MAPS_API_KEY`):

```bash
python cli.py --sov tests/test_sample_data/sample_sov.xlsx --module1 --module2 --module4 --module5
```

Slip extraction:

```bash
python cli.py --sov tests/test_sample_data/sample_sov.xlsx --module3 --slips tests/test_sample_data/sample_slip.pdf
```

Results module:

```bash
python cli.py --module6 --model-output tests/test_sample_data/sample_model_output.csv
```

### Tests

```bash
pip install pytest
pytest tests -q
```

## Folder layout

- `config/` — column keywords, mapping tables, RMS/AIR template stubs  
- `input/` — drop SOVs, slips, and vendor outputs here (optional; GUI uploads work too)  
- `output/` — cleaned SOVs, geocoded CSVs, slips JSON/XLSX, mapped SOVs, RMS/AIR exports, reports  
- `modules/` — processing engines (`module1` … `module6`)  
- `tests/` — unit tests and `test_sample_data/`  
- `logs/smartcat.log` — rotating operational log  

## API keys (optional / feature-specific)

| Variable | Purpose |
|----------|---------|
| `GOOGLE_MAPS_API_KEY` | Primary geocoding (Google Geocoding API) |
| `GOOGLE_TRANSLATE_API_KEY` | Non-English addresses → English before parsing |
| `OPENAI_API_KEY` | Optional LLM fallback for complex slip language |

**Privacy:** By default, PDF text is extracted locally (`pdfplumber`, optional OCR). Cloud APIs are invoked only when keys are configured and a module requires them.

## Tesseract OCR

**Windows:** Install [Tesseract at UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) or the official installer and add it to `PATH`.  

**macOS:** `brew install tesseract`  

**Linux:** `sudo apt install tesseract-ocr` (Debian/Ubuntu)

For `pdf2image`, install **Poppler** and ensure it is on `PATH` (Windows: poppler binaries alongside pdf2image docs).

## libpostal (optional)

Native **libpostal** gives high-quality international parsing but requires a C library build. This project uses **`usaddress`** for US-heavy portfolios and heuristic splitting elsewhere. To integrate libpostal later, install the library per [openvenues/libpostal](https://github.com/openvenues/libpostal) and the Python bindings (`postal`), then extend `address_parser.py`.

## Production notes

- Vendor **RMS RiskLink** and **AIR Touchstone** formats vary by client and version; validate exports against your template before production runs.
- For **100k+ locations**, pass chunk sizes via module APIs (`chunksize` on file methods) or split SOVs externally.
- Extend `config/occupancy_mapping.csv` and `config/construction_mapping.csv` with your master grading tables.

## License

Use and modify within your organization per your compliance policies. Third-party libraries retain their respective licenses.
