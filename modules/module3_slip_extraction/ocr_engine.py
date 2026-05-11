"""Tesseract OCR wrapper for scanned PDF pages."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from smartcat_logging import get_logger

logger = get_logger("module3.ocr")


def image_to_text(image: Image.Image, lang: str = "eng") -> str:
    try:
        import pytesseract

        return pytesseract.image_to_string(image, lang=lang) or ""
    except Exception as e:
        logger.warning("OCR failed: %s", e)
        return ""


def pdf_to_images_poppler(pdf_path: Path, dpi: int = 200) -> list[Image.Image]:
    """Rasterize PDF via pdf2image (requires Poppler on PATH)."""
    try:
        from pdf2image import convert_from_path

        return convert_from_path(str(pdf_path), dpi=dpi)
    except Exception as e:
        logger.warning("pdf2image/poppler unavailable: %s", e)
        return []
