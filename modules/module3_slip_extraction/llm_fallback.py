"""Optional OpenAI extraction for messy slips."""
from __future__ import annotations

import json
from typing import Any

from smartcat_logging import get_logger

logger = get_logger("module3.llm")


SYSTEM = """You extract structured insurance policy fields from slip text.
Return strict JSON with keys: tiv, tiv_currency, limits_occurrence, limits_aggregate,
sublimits (array of {peril, amount_or_status}), deductibles (array),
coinsurance_pct, sir, waiting_period ({hours, raw}), policy_form.
Use null when unknown."""


def extract_with_llm(text: str, api_key: str | None, model: str = "gpt-4o-mini") -> dict[str, Any] | None:
    if not api_key or not text.strip():
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": text[:24000]},
            ],
            temperature=0,
        )
        raw = resp.choices[0].message.content or "{}"
        return json.loads(raw)
    except Exception as e:
        logger.warning("LLM fallback failed: %s", e)
        return None
