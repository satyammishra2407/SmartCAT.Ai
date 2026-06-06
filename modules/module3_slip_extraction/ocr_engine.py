"""Tesseract OCR wrapper for scanned PDF pages."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from PIL import Image

from smartcat_logging import get_logger

logger = get_logger("module3.ocr")

_TESSERACT_PATHS = [
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
]


def _configure_tesseract() -> None:
    try:
        import pytesseract

        if shutil.which("tesseract"):
            return
        for p in _TESSERACT_PATHS:
            if p.exists():
                pytesseract.pytesseract.tesseract_cmd = str(p)
                return
        env = os.getenv("TESSERACT_CMD")
        if env and Path(env).exists():
            pytesseract.pytesseract.tesseract_cmd = env
    except Exception:
        pass


def image_to_text(image: Image.Image, lang: str = "eng") -> str:
    try:
        import pytesseract

        _configure_tesseract()
        return pytesseract.image_to_string(image, lang=lang) or ""
    except Exception as e:
        logger.warning("OCR failed: %s", e)
        return ""


def pdf_to_images_poppler(pdf_path: Path, dpi: int = 200) -> list[Image.Image]:
    """Rasterize PDF — PyMuPDF first, then pdf2image/poppler fallback."""
    import io

    try:
        import fitz

        images: list[Image.Image] = []
        doc = fitz.open(str(pdf_path))
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            images.append(Image.open(io.BytesIO(pix.tobytes("png"))))
        if images:
            return images
    except Exception as e:
        logger.debug("PyMuPDF rasterize failed: %s", e)

    try:
        from pdf2image import convert_from_path

        return convert_from_path(str(pdf_path), dpi=dpi)
    except Exception as e:
        logger.warning("pdf2image/poppler unavailable: %s", e)
        return []
