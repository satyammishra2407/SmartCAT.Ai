"""OpenAI Vision OCR fallback for scanned slips (Streamlit Cloud without Tesseract)."""
from __future__ import annotations

import base64
import io
from pathlib import Path

from smartcat_logging import get_logger

logger = get_logger("module3.vision")

_PROMPT = (
    "You are an OCR engine for insurance policy slips. "
    "Transcribe ALL visible text from this page exactly — every dollar amount, "
    "date, table row, limit, sublimit, deductible, and label. "
    "Preserve two-column tables as: Description<TAB>Value per line. "
    "Do not summarize or skip rows."
)


def ocr_pdf_with_vision(pdf_path: Path, api_key: str, max_pages: int = 12, dpi: int = 150) -> str:
    if not api_key:
        return ""
    try:
        import fitz
        from openai import OpenAI
        from PIL import Image
    except ImportError as e:
        logger.warning("Vision OCR dependencies missing: %s", e)
        return ""

    parts: list[str] = []
    try:
        client = OpenAI(api_key=api_key)
        doc = fitz.open(str(pdf_path))
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pix = page.get_pixmap(dpi=dpi)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.standard_b64encode(buf.getvalue()).decode("ascii")

            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": _PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "low"},
                            },
                        ],
                    }
                ],
                temperature=0,
                max_tokens=4096,
            )
            page_text = (resp.choices[0].message.content or "").strip()
            if page_text:
                parts.append(page_text)
    except Exception as e:
        logger.warning("Vision OCR failed for %s: %s", pdf_path.name, e)
    return "\n\n".join(parts)
