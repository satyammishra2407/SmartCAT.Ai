"""Split slip text into coarse sections (limits, deductibles, sublimits)."""
from __future__ import annotations

import re


def split_sections(text: str) -> dict[str, str]:
    """Very light keyword-based sections for targeted regex."""
    lower = text.lower()
    keys = {
        "limits": r"(limits?\s+of\s+liability|schedule\s+of\s+limits)",
        "deductibles": r"(deductible|deductibles)",
        "sublimits": r"(sublimit|sub[- ]limits)",
        "conditions": r"(waiting\s+period|coinsurance|participation)",
    }
    spans: list[tuple[int, str]] = []
    for name, pat in keys.items():
        for m in re.finditer(pat, lower):
            spans.append((m.start(), name))
    spans.sort()
    sections: dict[str, str] = {k: "" for k in keys}
    for i, (start, name) in enumerate(spans):
        end = spans[i + 1][0] if i + 1 < len(spans) else len(text)
        chunk = text[start:end]
        sections[name] = (sections[name] + "\n" + chunk).strip()
    if not any(sections.values()):
        sections["full"] = text
    return sections
