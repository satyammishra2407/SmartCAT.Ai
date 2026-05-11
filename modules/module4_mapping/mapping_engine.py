"""Map occupancy and construction using CSV tables + fuzzy match."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pandas as pd

from modules.module4_mapping.fuzzy_matcher import best_match
from modules.module4_mapping.scheme_selector import select_scheme
from modules.module4_mapping.secondary_modifier_mapper import detect_secondary_columns, extract_secondaries
from modules.module4_mapping.validity_checker import check_construction_region
from smartcat_logging import get_logger

logger = get_logger("module4.engine")


def _load_mapping_csv(path: Path) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            label = r.get("free_text") or r.get("text") or ""
            rows.append((label, dict(r)))
    return rows


class MappingEngine:
    def __init__(
        self,
        occupancy_csv: Path | None = None,
        construction_csv: Path | None = None,
    ):
        root = Path(__file__).resolve().parents[2] / "config"
        self.occ_path = occupancy_csv or root / "occupancy_mapping.csv"
        self.cons_path = construction_csv or root / "construction_mapping.csv"
        self._occ = _load_mapping_csv(self.occ_path)
        self._cons = _load_mapping_csv(self.cons_path)

    def map_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Expect columns including occupancy/construction free text and Country."""
        cols = list(df.columns)
        occ_col = self._pick_column(cols, ["occupancy", "occ", "building use", "property type"])
        cons_col = self._pick_column(cols, ["construction", "const", "building type", "structural"])
        country_col = self._pick_column(cols, ["country"])

        sec_map = detect_secondary_columns(cols)
        logger.info("Mapping columns occ=%s cons=%s country=%s", occ_col, cons_col, country_col)

        rows: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            rd = row.to_dict()
            country = str(rd.get(country_col, "") or "") if country_col else ""
            scheme = select_scheme(country)

            occ_text = str(rd.get(occ_col, "") or "") if occ_col else ""
            cons_text = str(rd.get(cons_col, "") or "") if cons_col else ""

            occ_payload, occ_score = best_match(occ_text, self._occ)
            cons_choices = [c for c in self._cons if (c[1].get("scheme") or "RMS").upper() == scheme]
            if not cons_choices:
                cons_choices = self._cons
            cons_payload, cons_score = best_match(cons_text, cons_choices)

            warnings: list[str] = []
            if cons_payload:
                warnings.extend(check_construction_region(str(cons_payload.get("code", "")), country))

            secondaries = extract_secondaries(rd, sec_map)

            rows.append(
                {
                    **rd,
                    "MappedOccupancyCode": occ_payload.get("code") if occ_payload else None,
                    "MappedOccupancyScheme": occ_payload.get("scheme") if occ_payload else None,
                    "OccupancyMatchScore": occ_score,
                    "MappedConstructionCode": cons_payload.get("code") if cons_payload else None,
                    "MappedConstructionScheme": scheme,
                    "ConstructionMatchScore": cons_score,
                    "mapping_warnings": "; ".join(warnings),
                    **{f"sec_{k}": v for k, v in secondaries.items()},
                }
            )

        return pd.DataFrame(rows)

    def _pick_column(self, columns: list[str], keywords: list[str]) -> str | None:
        for orig in columns:
            lc = str(orig).lower()
            for kw in keywords:
                if kw in lc:
                    return orig
        return None

    def map_file(self, input_path: Path, output_path: Path, chunksize: int | None = None) -> Path:
        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if input_path.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(input_path)
            out = self.map_dataframe(df)
            out.to_excel(output_path, index=False)
            return output_path

        if chunksize:
            first = True
            for chunk in pd.read_csv(input_path, chunksize=chunksize):
                out = self.map_dataframe(chunk)
                out.to_csv(output_path, mode="w" if first else "a", index=False, header=first)
                first = False
            return output_path

        df = pd.read_csv(input_path)
        out = self.map_dataframe(df)
        out.to_excel(output_path, index=False)
        return output_path
