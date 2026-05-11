"""Merge cleaned SOV + geocode + mapping + slip terms → RMS/AIR files."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from modules.module5_model_builder.air_formatter import write_air_csv
from modules.module5_model_builder.rms_formatter import write_rms_accounts, write_rms_locations
from modules.module5_model_builder.validator import validate_locations
from smartcat_logging import get_logger

logger = get_logger("module5.builder")


class ModelBuilderEngine:
    def build(
        self,
        df_locations: pd.DataFrame,
        slip_terms: dict[str, Any] | None,
        out_dir: Path,
        stem: str = "smartcat_export",
    ) -> dict[str, Any]:
        """
        Writes:
          {stem}_rms_locations.txt
          {stem}_rms_accounts.txt
          {stem}_air_locations.csv
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        rows = df_locations.to_dict("records")
        ok, msgs = validate_locations(rows)
        if not ok:
            logger.warning("Validation warnings: %s", msgs)

        rms_loc = out_dir / f"{stem}_rms_locations.txt"
        air_csv = out_dir / f"{stem}_air_locations.csv"
        rms_acc = out_dir / f"{stem}_rms_accounts.txt"

        _, rms_df = write_rms_locations(df_locations, rms_loc)
        write_rms_accounts(slip_terms, rms_df, rms_acc)
        write_air_csv(df_locations, air_csv, slip_terms=slip_terms)

        return {
            "rms_locations": rms_loc,
            "rms_accounts": rms_acc,
            "air_csv": air_csv,
            "validation_messages": msgs,
            "rms_row_count": len(rms_df),
        }
