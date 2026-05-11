"""Orchestrate column detection, parsing, validation, and standardized SOV output."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from modules.module1_address_scrubbing.address_parser import merge_components, parse_us_address
from modules.module1_address_scrubbing.column_detector import build_full_address_row, detect_columns
from modules.module1_address_scrubbing.national_address_handler import looks_japanese, preprocess_japan
from modules.module1_address_scrubbing.validator import normalize_postal_display, suggest_city_from_zip, validate_postal
from smartcat_logging import get_logger

logger = get_logger("module1.engine")

OUT_COLS = ["Street", "City", "State", "PostalCode", "Country"]


class AddressScrubbingEngine:
    def __init__(self, translate_api_key: str | None = None):
        self.translate_api_key = translate_api_key

    def scrub_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        mapping = detect_columns(list(df.columns))
        rows_out: list[dict[str, Any]] = []

        for _, row in df.iterrows():
            rd = row.to_dict()
            comp = self._row_to_components(rd, mapping)
            cc = comp.get("country") or "US"
            pc_raw = comp.get("postal_code")
            pc_norm = normalize_postal_display(pc_raw)
            if pc_norm and not validate_postal(pc_norm, cc[:2] if len(cc) == 2 else "US"):
                logger.warning("Postal format unusual for %s: %s", cc, pc)

            city = comp.get("city") or ""
            if (not city) and pc_norm and cc.upper() in ("US", "USA", ""):
                hint = suggest_city_from_zip(pc_norm)
                if hint:
                    comp["city"] = hint

            pc = pc_norm
            rows_out.append(
                {
                    **rd,
                    "Street": " ".join(filter(None, [comp.get("house_number", ""), comp.get("street", "")])).strip(),
                    "City": comp.get("city", ""),
                    "State": comp.get("state", ""),
                    "PostalCode": pc,
                    "Country": comp.get("country", "") or "US",
                }
            )

        return pd.DataFrame(rows_out)

    def _row_to_components(self, row: dict, mapping: dict[str, str | None]) -> dict[str, Any]:
        street_col = mapping.get("street")
        city_col = mapping.get("city")
        state_col = mapping.get("state")
        zip_col = mapping.get("postal_code")
        country_col = mapping.get("country")

        full = None
        if street_col and street_col in row:
            full = row.get(street_col)

        split_ok = city_col and state_col and zip_col and all(row.get(c) for c in (city_col, state_col, zip_col))

        if split_ok and not (full and "," in str(full)):
            return merge_components(
                "",
                str(row.get(street_col) or ""),
                str(row.get(city_col) or ""),
                str(row.get(state_col) or ""),
                str(row.get(zip_col) or ""),
                str(row.get(country_col) or "US"),
            )

        text = build_full_address_row(row, mapping) or (str(full) if full is not None else "")
        text = str(text).strip()
        if not text:
            return parse_us_address("")

        if looks_japanese(text):
            prep = preprocess_japan(text, self.translate_api_key)
            text = prep.get("translated") or text
            comp = parse_us_address(text)
            if prep.get("postal_hint") and not comp.get("postal_code"):
                comp["postal_code"] = prep["postal_hint"]
            comp["country"] = comp.get("country") or "JP"
            return comp

        return parse_us_address(text)

    def scrub_file(
        self,
        input_path: str | Path,
        output_path: str | Path,
        chunksize: int | None = None,
    ) -> Path:
        """Read Excel/CSV; optionally chunk large CSVs."""
        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        suffix = input_path.suffix.lower()
        if suffix in (".xlsx", ".xls"):
            df = pd.read_excel(input_path)
            out = self.scrub_dataframe(df)
            out.to_excel(output_path, index=False)
            logger.info("Wrote scrubbed SOV: %s (%s rows)", output_path, len(out))
            return output_path

        if chunksize:
            first = True
            total = 0
            for chunk in pd.read_csv(input_path, chunksize=chunksize):
                out = self.scrub_dataframe(chunk)
                out.to_csv(output_path, mode="w" if first else "a", index=False, header=first)
                first = False
                total += len(out)
            logger.info("Wrote scrubbed SOV (chunked): %s (%s rows)", output_path, total)
            return output_path

        df = pd.read_csv(input_path)
        out = self.scrub_dataframe(df)
        out.to_excel(output_path.with_suffix(".xlsx"), index=False)
        logger.info("Wrote scrubbed SOV: %s", output_path.with_suffix(".xlsx"))
        return output_path.with_suffix(".xlsx")
