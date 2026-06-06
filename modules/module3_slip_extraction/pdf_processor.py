"""Slip extraction engine — PDF, Word, images → structured tables."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from modules.module3_slip_extraction.document_loader import load_document
from modules.module3_slip_extraction.entity_extractor import extract_from_text
from modules.module3_slip_extraction.excel_exporter import save_excel, save_json
from modules.module3_slip_extraction.llm_fallback import extract_with_llm
from smartcat_logging import get_logger

logger = get_logger("module3.engine")

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}


class SlipExtractionEngine:
    def __init__(self, openai_key: str | None = None):
        self.openai_key = openai_key

    def extract_file(self, path: Path) -> dict[str, Any]:
        path = Path(path)
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise ValueError(f"Unsupported file type: {path.suffix}")

        full_text, method = load_document(path)
        structured = extract_from_text(full_text, source_file=path.name, extraction_method=method)

        if self._needs_llm(structured):
            llm = extract_with_llm(full_text, self.openai_key)
            if llm:
                structured = self._merge(structured, llm)

        structured["raw_text_preview"] = full_text[:3000]
        return structured

    def extract_pdf(self, pdf_path: Path) -> dict[str, Any]:
        """Backward-compatible alias."""
        return self.extract_file(pdf_path)

    def _needs_llm(self, s: dict[str, Any]) -> bool:
        if not self.openai_key:
            return False
        has_tiv = bool(s.get("tiv"))
        has_limit = bool(s.get("limit_of_liability") or s.get("blanket_limit"))
        has_rows = len(s.get("limits_sublimits") or []) >= 2
        return not has_tiv and not has_limit and not has_rows

    def _merge(self, base: dict[str, Any], llm: dict[str, Any]) -> dict[str, Any]:
        out = dict(base)
        for k, v in llm.items():
            if k in ("limits_sublimits", "deductibles", "waiting_periods"):
                continue
            if v not in (None, "", [], {}):
                out[k] = v
        return out

    def extract_many(self, paths: list[Path]) -> list[dict[str, Any]]:
        return [self.extract_file(p) for p in paths]

    def save_outputs(
        self,
        records: list[dict[str, Any]],
        json_path: Path,
        xlsx_path: Path,
    ) -> tuple[Path, Path]:
        save_json(records, json_path)
        save_excel(records, xlsx_path)
        return json_path, xlsx_path
