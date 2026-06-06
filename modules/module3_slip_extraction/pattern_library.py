"""Regex patterns for insurance slip fields."""
from __future__ import annotations

import re

TIV_PATTERNS = [
    re.compile(
        r"total\s+(?:insured|insurable)\s+value(?:\s*\(TIV\))?\s*[:]?\s*"
        r"([\$€£]?[\d,]+(?:\.\d+)?)\s*([A-Z]{3})?",
        re.I,
    ),
    re.compile(r"with\s+((?:US)?\$[\d,]+(?:\.\d+)?)\s+of\s+TIV", re.I),
    re.compile(r"TIV\s*[\(:]?\s*([\$€£]?[\d,]+(?:\.\d+)?)\s*([A-Z]{3})?", re.I),
    re.compile(r"(?:US)?\$([\d,]+(?:\.\d+)?)\s*(?:USD)?\s*(?:TIV|total\s+insurable)", re.I),
]

NAMED_INSURED = re.compile(
    r"(?:named\s+insured|insured)\s*[:]?\s*([A-Za-z0-9\s,\.&\-'()]+?)(?:\.|$|\n|TIV|Program)",
    re.I,
)

EFFECTIVE_DATE = re.compile(
    r"(?:effective\s+date|inception\s+date|incept(?:ion)?)\s*[:]?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
    re.I,
)
EXPIRATION_DATE = re.compile(
    r"(?:expiration\s+date|expiry\s+date|expir(?:y|ation))\s*[:]?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
    re.I,
)
POLICY_PERIOD = re.compile(
    r"(?:policy\s+period|period\s+of\s+insurance)\s*[:]?\s*([^\n]{10,120})",
    re.I,
)

LIMIT_OCC = re.compile(
    r"(?:limit|limits)\s+of\s+liability[^$\n]{0,80}?(?:occurrence|each\s+occurrence)\s*[:]?\s*((?:US)?\$[\d,]+(?:\.\d+)?)",
    re.I | re.S,
)
LIMIT_PROGRAM = re.compile(
    r"(?:program\s+limit\s+of\s+liability\s+is|program\s+limit)\s*[:]?\s*((?:US)?\$[\d,]+(?:\.\d+)?)",
    re.I,
)
LIMIT_AGG = re.compile(
    r"(?:annual\s+)?aggregate\s*(?:limit)?\s*[:]?\s*((?:US)?\$[\d,]+(?:\.\d+)?)",
    re.I,
)
BLANKET_LIMIT = re.compile(
    r"blanket\s+limit\s*[:]?\s*((?:US)?\$[\d,]+(?:\.\d+)?)",
    re.I,
)

DEDUCT_PCT = re.compile(
    r"(\d+(?:\.\d+)?)\s*%\s*(?:of\s*)?(?:TIV|total\s+(?:insured|insurable)\s+value|(?:the\s+)?value|actual\s+value)"
    r".*?(?:min(?:imum)?\s*(?:deductible\s*)?(?:of\s*)?((?:US)?\$[\d,]+))?"
    r".*?(?:max(?:imum)?\s*(?:deductible\s*)?(?:of\s*)?((?:US)?\$[\d,]+))?",
    re.I | re.S,
)
DEDUCT_FIXED = re.compile(
    r"(?:blanket\s+)?deductible\s*[:]?\s*((?:US)?\$[\d,]+(?:\.\d+)?)",
    re.I,
)
BLANKET_DED = re.compile(
    r"blanket\s+deductible\s*[:]?\s*((?:US)?\$[\d,]+(?:\.\d+)?)",
    re.I,
)

COINSURANCE = re.compile(
    r"(?:coinsurance|participation|line\s+size)\s*[\(:]?\s*(\d+(?:\.\d+)?)\s*%",
    re.I,
)
PART_OF = re.compile(
    r"(\$[\d,]+(?:\.\d+)?|\d+(?:\.\d+)?%)\s+part\s+of\s+(\$[\d,]+(?:\.\d+)?|\d+(?:\.\d+)?%)",
    re.I,
)
EXCESS_OF = re.compile(
    r"(?:excess\s+of|xs|attachment\s+point)\s*[:]?\s*((?:US)?\$[\d,]+(?:\.\d+)?|\d+(?:\.\d+)?%)",
    re.I,
)
SIR = re.compile(
    r"(?:SIR|self[- ]insured\s+retention(?:\s*\(SIR\))?)\s*[:]?\s*((?:US)?\$[\d,]+(?:\.\d+)?)",
    re.I,
)

WAITING = re.compile(
    r"waiting\s+period\s*[:]?\s*(\d+)\s*(hour|hours|day|days|hr|hrs)",
    re.I,
)

POLICY_FORM = re.compile(
    r"(?:policy\s+form|form\s+of\s+coverage|marsh\s+manuscript\s+form)\s*[:]?\s*([A-Za-z0-9\-\/ \(\)]+)",
    re.I,
)

LOSS_HISTORY = re.compile(
    r"((?:clean|no)\s+\d+\s*year\s+loss\s+history|loss\s+history\s*[:]?\s*[^\n]+)",
    re.I,
)

TIV_NOTES = re.compile(
    r"(?:N\.B\.|note|notes)\s*[:]?\s*([^\n]{5,200})",
    re.I,
)

SUBLIMIT_PERIL = re.compile(
    r"(Earth\s+Movement|Earthquake|Flood|Named\s+Storm|Named\s+Windstorm|Wind|Hurricane|Wildfire)"
    r"[^\n\$]{0,120}?"
    r"((?:US)?\$[\d,]+(?:\.\d+)?|Excluded|Included|N/A)",
    re.I,
)

MIN_DED = re.compile(r"min(?:imum)?\s*(?:deductible\s*)?(?:of\s*)?((?:US)?\$[\d,]+)", re.I)
MAX_DED = re.compile(r"max(?:imum)?\s*(?:deductible\s*)?(?:of\s*)?((?:US)?\$[\d,]+)", re.I)


def clean_money(s: str | None) -> str | None:
    if not s:
        return None
    m = re.search(r"([\d,]+(?:\.\d+)?)", str(s).replace("US", "").replace("$", ""))
    if not m:
        return None
    raw = m.group(1)
    groups = raw.split(",")
    # OCR typo: trailing group "0000" instead of "000"
    if len(groups) > 1 and len(groups[-1]) == 4 and set(groups[-1]) <= {"0"}:
        groups[-1] = groups[-1][:3]
    normalized = "".join(groups)
    cleaned = re.sub(r"[^\d.]", "", normalized)
    return cleaned if cleaned else None


def parse_money_from_text(s: str) -> str | None:
    m = re.search(r"(?:US)?\$([\d,]+(?:\.\d+)?)", s)
    return clean_money(m.group(1)) if m else None
