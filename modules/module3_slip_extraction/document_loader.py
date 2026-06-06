"""Load slip documents: PDF, Word, images."""
from __future__ import annotations

import io
from pathlib import Path

from smartcat_logging import get_logger

logger = get_logger("module3.loader")

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}
DOCX_SUFFIX = {".docx"}
PDF_SUFFIX = {".pdf"}


def load_document(path: Path) -> tuple[str, str]:
    """
    Return (full_text, extraction_method).
    extraction_method: text_pdf | ocr_pdf | ocr_image | docx | empty
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix in PDF_SUFFIX:
        return _load_pdf(path)
    if suffix in DOCX_SUFFIX:
        return _load_docx(path), "docx"
    if suffix in IMAGE_SUFFIXES:
        return _load_image(path), "ocr_image"
    raise ValueError(f"Unsupported slip format: {suffix} ({path.name})")


def _load_pdf(path: Path) -> tuple[str, str]:
    import pdfplumber

    text_parts: list[str] = []
    table_parts: list[str] = []

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            if t.strip():
                text_parts.append(t)
            for table in page.extract_tables() or []:
                for row in table:
                    if not row:
                        continue
                    cells = [str(c or "").strip() for c in row if c]
                    if len(cells) >= 2:
                        table_parts.append(f"{cells[0]}\t{cells[-1]}")
                    elif len(cells) == 1:
                        table_parts.append(cells[0])

    full_text = "\n".join(text_parts).strip()
    if table_parts:
        full_text = full_text + "\n\n" + "\n".join(table_parts)

    if len(full_text.replace("\t", "").strip()) >= 80:
        return full_text, "text_pdf"

    ocr_text = _ocr_pdf_pages(path)
    if ocr_text.strip():
        return ocr_text, "ocr_pdf"
    return full_text, "text_pdf"


def _ocr_pdf_pages(path: Path) -> str:
    try:
        import fitz
    except ImportError:
        logger.warning("PyMuPDF not installed — cannot OCR scanned PDF %s", path.name)
        return ""

    from modules.module3_slip_extraction.ocr_engine import image_to_text

    parts: list[str] = []
    try:
        doc = fitz.open(path)
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            from PIL import Image

            img = Image.open(io.BytesIO(pix.tobytes("png")))
            t = image_to_text(img)
            if t.strip():
                parts.append(t)
    except Exception as e:
        logger.warning("PDF OCR failed for %s: %s", path.name, e)
    return "\n\n".join(parts)


def _load_docx(path: Path) -> str:
    from docx import Document

    doc = Document(str(path))
    parts: list[str] = []
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text.strip())
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if len(cells) >= 2:
                parts.append(f"{cells[0]}\t{cells[-1]}")
            elif cells:
                parts.append(cells[0])
    return "\n".join(parts)


def _load_image(path: Path) -> str:
    from PIL import Image

    from modules.module3_slip_extraction.ocr_engine import image_to_text

    img = Image.open(path)
    return image_to_text(img)
