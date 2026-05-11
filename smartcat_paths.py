"""Central project paths."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = PROJECT_ROOT / "config"
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"
LOG_DIR = PROJECT_ROOT / "logs"

for _p in (
    INPUT_DIR / "sovs",
    INPUT_DIR / "slips",
    INPUT_DIR / "model_outputs",
    OUTPUT_DIR / "cleaned_sovs",
    OUTPUT_DIR / "geocoded",
    OUTPUT_DIR / "extracted_slips",
    OUTPUT_DIR / "mapped_codes",
    OUTPUT_DIR / "model_imports",
    OUTPUT_DIR / "reports",
    LOG_DIR,
):
    _p.mkdir(parents=True, exist_ok=True)
