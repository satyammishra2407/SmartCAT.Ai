#!/usr/bin/env python3
"""Run selected SmartCAT.AI modules end-to-end."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from modules.module1_address_scrubbing import AddressScrubbingEngine
from modules.module2_geocoding import GeocodingEngine
from modules.module3_slip_extraction import SlipExtractionEngine
from modules.module4_mapping import MappingEngine
from modules.module5_model_builder import ModelBuilderEngine
from modules.module6_results import ResultsInterpretationEngine
from smartcat_logging import setup_logging
from smartcat_paths import OUTPUT_DIR

load_dotenv()

logger = setup_logging()


def _load_sov(path: Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path)
    return pd.read_csv(path)


def run_pipeline(args: argparse.Namespace) -> None:
    google_key = args.google_maps_key or os.getenv("GOOGLE_MAPS_API_KEY")
    translate_key = args.translate_key or os.getenv("GOOGLE_TRANSLATE_API_KEY")
    openai_key = args.openai_key or os.getenv("OPENAI_API_KEY")

    stem = Path(args.sov).stem if args.sov else "pipeline"

    df: pd.DataFrame | None = None
    if args.sov:
        df = _load_sov(Path(args.sov))

    slip_terms: dict | None = None

    if args.module1:
        if df is None:
            raise SystemExit("--sov is required when running module 1")
        m1 = AddressScrubbingEngine(translate_api_key=translate_key)
        df = m1.scrub_dataframe(df)
        out_xlsx = OUTPUT_DIR / "cleaned_sovs" / f"{stem}_scrubbed.xlsx"
        out_xlsx.parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(out_xlsx, index=False)
        logger.info("Module1 complete: %s (%s rows)", out_xlsx, len(df))

    if args.module2:
        if df is None:
            raise SystemExit("--sov is required when running module 2 (run after module 1 or supply cleaned SOV)")
        m2 = GeocodingEngine(
            google_maps_key=google_key,
            audit_path=OUTPUT_DIR / "geocoded" / "geocode_audit.csv",
        )
        df = m2.geocode_dataframe(df)
        geo_csv = OUTPUT_DIR / "geocoded" / f"{stem}_geocoded.csv"
        geo_csv.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(geo_csv, index=False)
        logger.info("Module2 complete: %s", geo_csv)

    if args.module3:
        if not args.slips:
            raise SystemExit("--slips required for module 3")
        m3 = SlipExtractionEngine(openai_key=openai_key)
        pdfs = [Path(p.strip()) for p in args.slips.split(",") if p.strip()]
        recs = m3.extract_many(pdfs)
        json_path = OUTPUT_DIR / "extracted_slips" / f"{stem}_slips.json"
        xlsx_path = OUTPUT_DIR / "extracted_slips" / f"{stem}_slips.xlsx"
        json_path.parent.mkdir(parents=True, exist_ok=True)
        m3.save_outputs(recs, json_path, xlsx_path)
        slip_terms = recs[0] if recs else None
        logger.info("Module3 complete: %s slips", len(recs))

    if args.module4:
        if df is None:
            raise SystemExit("--sov path required for module 4")
        m4 = MappingEngine()
        df = m4.map_dataframe(df)
        mapped_xlsx = OUTPUT_DIR / "mapped_codes" / f"{stem}_mapped.xlsx"
        mapped_xlsx.parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(mapped_xlsx, index=False)
        logger.info("Module4 complete: %s", mapped_xlsx)

    if args.module5:
        if df is None:
            raise SystemExit("Module 5 requires SOV data in memory — run prior modules in same command")
        m5 = ModelBuilderEngine()
        imp_dir = OUTPUT_DIR / "model_imports"
        imp_dir.mkdir(parents=True, exist_ok=True)
        paths = m5.build(df, slip_terms, imp_dir, stem=stem)
        logger.info("Module5 outputs: %s", paths)

    if args.module6:
        if not args.model_output:
            raise SystemExit("--model-output required for module 6")
        m6 = ResultsInterpretationEngine(OUTPUT_DIR / "reports")
        outs = m6.run(Path(args.model_output), stem=f"{stem}_results")
        logger.info("Module6 outputs: %s", outs)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="SmartCAT.AI pipeline runner")
    p.add_argument("--sov", help="Path to SOV Excel/CSV")
    p.add_argument("--slips", help="Comma-separated PDF paths")
    p.add_argument("--model-output", dest="model_output", help="Model EP/output CSV")
    p.add_argument("--google-maps-key", dest="google_maps_key", default=None)
    p.add_argument("--translate-key", dest="translate_key", default=None)
    p.add_argument("--openai-key", dest="openai_key", default=None)
    p.add_argument("--module1", action="store_true", help="Address scrubbing")
    p.add_argument("--module2", action="store_true", help="Geocoding")
    p.add_argument("--module3", action="store_true", help="Slip extraction")
    p.add_argument("--module4", action="store_true", help="Occ/construction mapping")
    p.add_argument("--module5", action="store_true", help="Model import builder")
    p.add_argument("--module6", action="store_true", help="Results interpretation")
    return p


if __name__ == "__main__":
    parser = build_parser()
    ns = parser.parse_args()
    run_pipeline(ns)
