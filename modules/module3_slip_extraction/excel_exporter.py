"""Multi-sheet Excel export for slip extraction."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def records_to_frames(records: list[dict[str, Any]]) -> dict[str, pd.DataFrame]:
    summaries: list[dict[str, Any]] = []
    limits: list[dict[str, Any]] = []
    deductibles: list[dict[str, Any]] = []
    waiting: list[dict[str, Any]] = []
    cat_summary: list[dict[str, Any]] = []

    for rec in records:
        flat = {k: v for k, v in rec.items() if k not in (
            "limits_sublimits", "deductibles", "waiting_periods",
            "cat_peril_summary", "raw_text_preview",
        )}
        summaries.append(flat)
        limits.extend(rec.get("limits_sublimits") or [])
        deductibles.extend(rec.get("deductibles") or [])
        waiting.extend(rec.get("waiting_periods") or [])

        for row in rec.get("cat_peril_summary") or []:
            cat_summary.append(
                {
                    "source_file": rec.get("source_file"),
                    "peril_code": row.get("peril_code"),
                    "peril_name": row.get("peril_name"),
                    "primary_limit": row.get("primary_limit"),
                    "limit_status": row.get("limit_status"),
                    "sublimit_count": row.get("sublimit_count"),
                    "deductible_count": row.get("deductible_count"),
                    "primary_deductible_json": json.dumps(row.get("primary_deductible"), default=str),
                }
            )

    return {
        "Policy Summary": pd.DataFrame(summaries),
        "Limits & Sublimits": pd.DataFrame(limits) if limits else pd.DataFrame(columns=["source_file", "description", "amount"]),
        "Deductibles": pd.DataFrame(deductibles) if deductibles else pd.DataFrame(columns=["source_file", "peril", "amount"]),
        "Waiting Periods": pd.DataFrame(waiting) if waiting else pd.DataFrame(columns=["source_file", "coverage", "hours"]),
        "CAT Peril Summary": pd.DataFrame(cat_summary) if cat_summary else pd.DataFrame(columns=["peril_code", "primary_limit"]),
    }


def save_excel(records: list[dict[str, Any]], xlsx_path: Path) -> Path:
    xlsx_path = Path(xlsx_path)
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    frames = records_to_frames(records)
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        for sheet, df in frames.items():
            df.to_excel(writer, sheet_name=sheet[:31], index=False)
    return xlsx_path


def save_json(records: list[dict[str, Any]], json_path: Path) -> Path:
    json_path = Path(json_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, default=str)
    return json_path
