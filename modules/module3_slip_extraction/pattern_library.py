"""Regex patterns for insurance slip fields."""
from __future__ import annotations

import re

TIV_PATTERNS = [
    re.compile(
        r"total\s+(?:insured|insurable)\s+value\s*[:]?\s*([\$€£]?[\d,]+(?:\.\d+)?)\s*([A-Z]{3})?",
        re.I,
    ),
    re.compile(r"TIV\s*[:]?\s*([\$€£]?[\d,]+(?:\.\d+)?)\s*([A-Z]{3})?", re.I),
]

LIMIT_OCC = re.compile(
    r"(?:limit|limits)\s+of\s+liability.*?(?:occurrence|each\s+occurrence)\s*[:]?\s*([\$€£]?[\d,]+(?:\.\d+)?)",
    re.I | re.S,
)
LIMIT_AGG = re.compile(
    r"(?:aggregate|annual\s+aggregate)\s*(?:limit)?\s*[:]?\s*([\$€£]?[\d,]+(?:\.\d+)?)",
    re.I,
)

DEDUCT_PCT = re.compile(
    r"(\d+(?:\.\d+)?)\s*%\s*(?:of\s*)?(?:TIV|total\s+insured\s+value).*?(?:min(?:imum)?\s*([\$€£]?[\d,]+))?.*?(?:max(?:imum)?\s*([\$€£]?[\d,]+))?",
    re.I | re.S,
)
DEDUCT_FIXED = re.compile(r"(?:deductible)\s*[:]?\s*([\$€£]?[\d,]+(?:\.\d+)?)", re.I)

COINSURANCE = re.compile(r"(?:coinsurance|participation)\s*[:]?\s*(\d+(?:\.\d+)?)\s*%", re.I)
SIR = re.compile(r"(?:SIR|self[- ]insured\s+retention)\s*[:]?\s*([\$€£]?[\d,]+(?:\.\d+)?)", re.I)

WAITING = re.compile(
    r"waiting\s+period\s*[:]?\s*(\d+)\s*(hour|hours|day|days|hr|hrs)",
    re.I,
)

POLICY_FORM = re.compile(r"(?:policy\s+form|form\s+of\s+coverage)\s*[:]?\s*([A-Za-z0-9\-\/ ]+)", re.I)

SUBLIMIT_PERIL = re.compile(
    r"(Flood|Earthquake|Named\s+Storm|Wind|Hurricane|Wildfire)[^\n]*?([\$€£]?[\d,]+(?:\.\d+)?|Excluded)",
    re.I,
)


def clean_money(s: str | None) -> str | None:
    if not s:
        return None
    return s.strip().replace(",", "")
