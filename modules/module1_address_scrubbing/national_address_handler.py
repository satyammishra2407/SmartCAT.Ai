"""Non-English / national address helpers (Japan, etc.)."""
from __future__ import annotations

import re
from typing import Any

import requests

from smartcat_logging import get_logger

logger = get_logger("module1.national")


def looks_japanese(text: str) -> bool:
    if not text:
        return False
    # Hiragana, Katakana, Kanji ranges + Japanese postal symbol
    return bool(re.search(r"[〒ぁ-んァ-ン一-龥]", text))


def extract_jp_postal(text: str) -> str | None:
    m = re.search(r"〒?\s*(\d{3})\s*[-−]?\s*(\d{4})", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return None


def translate_text(text: str, api_key: str | None, target: str = "en") -> str:
    """
    Translate via Google Cloud Translate REST v2 when API key is set.
    Without a key, returns original text (local-only mode).
    """
    if not api_key or not text.strip():
        return text

    url = "https://translation.googleapis.com/language/translate/v2"
    try:
        r = requests.post(
            url,
            params={"key": api_key},
            json={"q": text, "target": target, "format": "text"},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        return data["data"]["translations"][0]["translatedText"]
    except Exception as e:
        logger.warning("Translate failed: %s", e)
        return text


def preprocess_japan(text: str, translate_key: str | None) -> dict[str, Any]:
    """Pull postal code; optionally translate to romaji/English for downstream parsing."""
    postal = extract_jp_postal(text) or ""
    trans = translate_text(text, translate_key) if translate_key else text
    return {"original": text, "postal_hint": postal, "translated": trans}
