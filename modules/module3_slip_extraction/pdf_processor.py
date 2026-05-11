"""PDF text + OCR pipeline and export."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pdfplumber
import pandas as pd

from modules.module3_slip_extraction.entity_extractor import extract_from_text
from modules.module3_slip_extraction.llm_fallback import extract_with_llm
from modules.module3_slip_extraction.ocr_engine import image_to_text, pdf_to_images_poppler
from smartcat_logging import get_logger

logger = get_logger("module3.pdf")


class SlipExtractionEngine:
    def __init__(self, openai_key: str | None = None):
        self.openai_key = openai_key

    def extract_pdf(self, pdf_path: Path) -> dict[str, Any]:
        pdf_path = Path(pdf_path)
        text_parts: list[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                text_parts.append(t)

        full_text = "\n".join(text_parts).strip()
        if len(full_text) < 40:
            logger.info("Sparse text in %s — trying OCR", pdf_path.name)
            for img in pdf_to_images_poppler(pdf_path):
                full_text += "\n" + image_to_text(img)

        structured = extract_from_text(full_text)
        if self._needs_llm(structured):
            llm = extract_with_llm(full_text, self.openai_key)
            if llm:
                structured = self._merge(structured, llm)

        structured["source_file"] = pdf_path.name
        structured["raw_text_preview"] = full_text[:2000]
        return structured

    def _needs_llm(self, s: dict[str, Any]) -> bool:
        return not s.get("tiv") and not s.get("limits_occurrence")

    def _merge(self, base: dict[str, Any], llm: dict[str, Any]) -> dict[str, Any]:
        out = dict(base)
        for k, v in llm.items():
            if v not in (None, "", [], {}):
                out[k] = v
        return out

    def extract_many(self, paths: list[Path]) -> list[dict[str, Any]]:
        return [self.extract_pdf(p) for p in paths]

    def save_outputs(self, records: list[dict[str, Any]], json_path: Path, xlsx_path: Path) -> tuple[Path, Path]:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, default=str)

        flat_rows: list[dict[str, Any]] = []
        for r in records:
            row = {k: v for k, v in r.items() if k not in ("raw_text_preview",)}
            if isinstance(row.get("sublimits"), list):
                row["sublimits"] = json.dumps(row["sublimits"])
            if isinstance(row.get("deductibles"), list):
                row["deductibles"] = json.dumps(row["deductibles"])
            flat_rows.append(row)

        pd.DataFrame(flat_rows).to_excel(xlsx_path, index=False)
        return json_path, xlsx_path
