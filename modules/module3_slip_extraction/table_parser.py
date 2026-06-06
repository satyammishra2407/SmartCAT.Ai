"""Parse two-column limit/deductible tables from slip text."""
from __future__ import annotations

import re
from typing import Any

from modules.module3_slip_extraction import pattern_library as pl

# Peril → RMS code
PERIL_CODES: list[tuple[str, str]] = [
    ("earth movement", "EQ"),
    ("earthquake", "EQ"),
    ("seismic", "EQ"),
    ("named storm", "WS"),
    ("named windstorm", "WS"),
    ("windstorm", "WS"),
    ("hurricane", "WS"),
    ("typhoon", "WS"),
    ("cyclone", "WS"),
    ("flood", "FL"),
    ("sturmflut", "FL"),
    ("wildfire", "WF"),
    ("severe convective", "SCS"),
    ("terrorism", "TR"),
    ("all other peril", "FR"),
    ("aop", "FR"),
]

PARENT_PERIL_HINTS = ("except", "aggregate limits which are a part of", "following per occurrence")

LIMIT_KEYWORDS = (
    "limit of liability",
    "program limit",
    "limits of liability",
    "blanket limit",
    "aggregate",
    "sublimit",
)

DEDUCTIBLE_SECTION = re.compile(r"deductible", re.I)
WAITING_KEYWORDS = ("waiting period", "hours", " days", " day")


def parse_limit_rows(text: str, source_file: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    in_deductible = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if DEDUCTIBLE_SECTION.search(line) and "limit" not in line.lower():
            in_deductible = True
            continue
        if in_deductible:
            continue

        pair = _split_row(line)
        if not pair:
            continue
        desc, val = pair
        if _looks_like_deductible_row(desc):
            continue

        row = _build_limit_row(desc, val, source_file)
        if row:
            rows.append(row)

    _link_parent_sublimits(rows)
    return rows


def parse_deductible_rows(text: str, source_file: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    in_section = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        lower = line.lower()
        if "deductible" in lower and ("application" in lower or lower.startswith("deductible")):
            in_section = True
            if _split_row(line):
                pass
            elif lower in ("deductibles", "deductible(s)", "g. deductible(s)"):
                continue
        if "waiting period" in lower and "deductible" not in lower:
            in_section = False

        pair = _split_row(line)
        if not pair:
            if in_section and re.search(r"\$\d|%\s*of|\d+\s*hours|\d+\s*days", line, re.I):
                pair = (line, "")
            else:
                continue

        desc, val = pair
        if not in_section and not _looks_like_deductible_row(desc):
            continue
        if not _looks_like_deductible_row(desc) and not val:
            continue

        row = _build_deductible_row(desc, val, source_file)
        if row:
            rows.append(row)

    return rows


def parse_waiting_periods(text: str, source_file: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    patterns = [
        (
            re.compile(
                r"(service\s+interruption|time\s+element|business\s+interruption)[^\n]{0,80}?"
                r"(\d+)\s*(hour|hours|hr|hrs|day|days)\b",
                re.I,
            ),
            1,
            2,
            3,
        ),
        (
            re.compile(r"waiting\s+period[^\n]{0,40}?(\d+)\s*(hour|hours|hr|hrs|day|days)", re.I),
            None,
            1,
            2,
        ),
        (
            re.compile(r"extended\s+period\s+of\s+liability[^\n]{0,30}?(\d+)\s*(day|days)", re.I),
            None,
            1,
            2,
        ),
    ]

    for pat, cov_g, amt_g, unit_g in patterns:
        for m in pat.finditer(text):
            coverage = (
                m.group(cov_g).strip()
                if cov_g and m.lastindex and m.lastindex >= cov_g and m.group(cov_g)
                else "General"
            )
            amt = int(m.group(amt_g))
            unit = m.group(unit_g).lower()
            hours = amt * 24 if "day" in unit else amt
            key = f"{coverage}|{hours}"
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "source_file": source_file,
                    "coverage": coverage.title() if coverage else "General",
                    "hours": hours,
                    "days": round(hours / 24, 2) if hours >= 24 else None,
                    "raw": m.group(0).strip()[:200],
                }
            )

    return rows


def build_cat_peril_summary(
    limits: list[dict[str, Any]],
    deductibles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    codes = ["EQ", "WS", "FL", "FR"]
    summary: list[dict[str, Any]] = []

    for code in codes:
        code_limits = [r for r in limits if r.get("peril_code") == code]
        code_deds = [r for r in deductibles if r.get("peril_code") == code]

        primary_limit = next((r for r in code_limits if r.get("row_type") == "limit"), None)
        if not primary_limit:
            primary_limit = next((r for r in code_limits if not r.get("parent_peril")), None)

        sublimits = [r for r in code_limits if r.get("row_type") == "sublimit" or r.get("parent_peril")]

        summary.append(
            {
                "peril_code": code,
                "peril_name": _code_name(code),
                "primary_limit": primary_limit.get("amount") if primary_limit else None,
                "limit_status": primary_limit.get("status") if primary_limit else None,
                "sublimit_count": len(sublimits),
                "sublimits_json": sublimits[:20],
                "deductible_count": len(code_deds),
                "primary_deductible": code_deds[0] if code_deds else None,
                "deductibles_json": code_deds[:20],
            }
        )
    return summary


def _split_row(line: str) -> tuple[str, str] | None:
    if "\t" in line:
        parts = line.split("\t", 1)
        return parts[0].strip(), parts[1].strip()

    # Trailing value: $..., Included, Excluded, N/A, digits+Days/Hours, pct
    m = re.match(
        r"^(.+?)\s+("
        r"(?:US)?\$[\d,]+(?:\.\d+)?(?:\s*/\s*(?:US)?\$[\d,]+(?:\.\d+)?)*"
        r"|Included|Excluded|N/A"
        r"|\d+(?:\.\d+)?\s*%[^$]*(?:\$[\d,]+[^$]*)*"
        r"|\d+\s*(?:Days?|Hours?|Hrs?)"
        r")\s*$",
        line,
        re.I,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # Limit of Liability: $200,000,000
    m2 = re.match(r"^(.+?)[:]\s*((?:US)?\$[\d,]+(?:\.\d+)?|Included|Excluded)\s*$", line, re.I)
    if m2:
        return m2.group(1).strip(), m2.group(2).strip()

    return None


def _build_limit_row(desc: str, val: str, source_file: str) -> dict[str, Any] | None:
    if len(desc) < 3:
        return None

    peril, code = _detect_peril(desc)
    lower = desc.lower()

    row_type = "coverage_extension"
    if "limit of liability" in lower or "program limit" in lower:
        row_type = "limit"
    elif any(k in lower for k in ("earth movement", "earthquake", "flood", "named storm", "windstorm")):
        row_type = "sublimit"
    elif "sublimit" in lower or "except not to exceed" in lower:
        row_type = "sublimit"
    elif re.search(r"\$\d", val):
        row_type = "sublimit"

    status = "active"
    amount = None
    vl = val.lower().strip()
    if vl in ("included",):
        status = "included"
    elif "excluded" in vl:
        status = "excluded"
    elif vl in ("n/a", "na"):
        status = "n/a"
    else:
        amount = pl.clean_money(val) or val

    basis = "occurrence"
    if "annual aggregate" in lower or "policy year" in lower:
        basis = "annual_aggregate"
    elif "aggregate" in lower:
        basis = "aggregate"

    region = _detect_region(desc)

    return {
        "source_file": source_file,
        "row_type": row_type,
        "description": desc[:500],
        "peril": peril,
        "peril_code": code,
        "region": region,
        "amount": amount,
        "currency": "USD" if "$" in val or not val else None,
        "status": status,
        "basis": basis,
        "parent_peril": None,
        "rms_field": "PARTOF" if row_type in ("limit", "sublimit") else None,
    }


def _build_deductible_row(desc: str, val: str, source_file: str) -> dict[str, Any] | None:
    if len(desc) < 2:
        return None

    lower = desc.lower()
    peril, code = _detect_peril(desc)
    if not peril and "combined" in lower:
        peril, code = "AOP", "FR"
    if "all other" in lower and not peril:
        peril, code = "AOP", "FR"

    ded_type = "monetary"
    amount = None
    pct = None
    min_amt = None
    max_amt = None
    waiting_hours = None

    combined = f"{desc} {val}".strip()
    vl = val.lower() if val else combined.lower()

    if "excluded" in vl or "excluded" in lower:
        ded_type = "excluded"
    elif re.search(r"\d+\s*(?:hour|hours|hr|hrs|day|days)\b", combined, re.I):
        ded_type = "waiting_period"
        wm = re.search(r"(\d+)\s*(hour|hours|hr|hrs|day|days)", combined, re.I)
        if wm:
            n = int(wm.group(1))
            waiting_hours = n * 24 if "day" in wm.group(2).lower() else n
    elif re.search(r"\d+(?:\.\d+)?\s*%\s*of", combined, re.I):
        ded_type = "hybrid" if re.search(r"min|max", combined, re.I) else "percent"
        pm = re.search(r"(\d+(?:\.\d+)?)\s*%\s*of", combined, re.I)
        if pm:
            pct = float(pm.group(1))
        min_amt = _extract_min(combined)
        max_amt = _extract_max(combined)
    elif val:
        amount = pl.clean_money(val)

    if not val and ded_type == "monetary":
        pm = re.search(r"(\d+(?:\.\d+)?)\s*%\s*of", desc, re.I)
        if pm:
            ded_type = "percent"
            pct = float(pm.group(1))
            min_amt = _extract_min(desc)
            max_amt = _extract_max(desc)
        else:
            am = re.search(r"(?:US)?\$([\d,]+(?:\.\d+)?)", desc)
            if am:
                amount = am.group(1).replace(",", "")

    cov = "combined"
    if "property damage" in lower or re.search(r"\bpd\b", lower):
        cov = "property_damage"
    elif "time element" in lower or re.search(r"\bte\b", lower) or "business interruption" in lower:
        cov = "time_element"
    elif "contents" in lower:
        cov = "contents"
    elif "building" in lower:
        cov = "building"

    basis = "per_occurrence"
    if "per location" in lower:
        basis = "per_location"
    elif "per building" in lower:
        basis = "per_building"
    elif "per unit" in lower:
        basis = "per_unit"

    if ded_type == "waiting_period":
        return None  # handled by waiting_periods parser

    return {
        "source_file": source_file,
        "peril": peril or desc[:80],
        "peril_code": code,
        "region": _detect_region(desc),
        "hazard_zone": _detect_hazard_zone(desc),
        "coverage_type": cov,
        "deductible_type": ded_type,
        "amount": amount,
        "pct": pct,
        "min_amount": min_amt,
        "max_amount": max_amt,
        "basis": basis,
        "waiting_hours": waiting_hours,
        "notes": val[:300] if val and len(val) > 20 else None,
        "rms_field": "BLANDEDAMT" if code else None,
    }


def _link_parent_sublimits(rows: list[dict[str, Any]]) -> None:
    current_parent: str | None = None
    for row in rows:
        desc = row.get("description", "")
        lower = desc.lower()
        if row.get("row_type") == "sublimit" and not any(h in lower for h in PARENT_PERIL_HINTS):
            if row.get("peril") and " - " not in desc and "except" not in lower:
                current_parent = row.get("peril")
        if " - " in desc or any(h in lower for h in PARENT_PERIL_HINTS):
            row["row_type"] = "sublimit"
            if current_parent:
                row["parent_peril"] = current_parent


def _detect_peril(text: str) -> tuple[str | None, str | None]:
    lower = text.lower()
    for name, code in PERIL_CODES:
        if name in lower:
            return name.title(), code
    return None, None


def _detect_region(text: str) -> str | None:
    regions = [
        "California", "New Madrid", "Pacific Northwest", "Japan", "Mexico", "Hawaii", "Alaska",
        "Puerto Rico", "Netherlands", "Thailand", "Europe", "South Africa", "LA County",
        "Los Angeles", "Special Flood Hazard Area", "SFHA", "MFHA", "Tier 1",
    ]
    found = [r for r in regions if r.lower() in text.lower()]
    return "; ".join(found) if found else None


def _detect_hazard_zone(text: str) -> str | None:
    lower = text.lower()
    if "high hazard" in lower:
        return "High Hazard"
    if "moderate hazard" in lower:
        return "Moderate Hazard"
    if "special flood hazard" in lower or "sfha" in lower:
        return "SFHA"
    return None


def _looks_like_deductible_row(desc: str) -> bool:
    lower = desc.lower()
    keys = (
        "deductible", "earth movement", "earthquake", "flood", "named storm",
        "aop", "all other", "combined all coverages", "property damage",
        "service interruption", "transit", "equipment breakdown", "per occurrence",
        "tier 1", "sfha", "mfha",
    )
    return any(k in lower for k in keys)


def _extract_min(text: str) -> str | None:
    m = re.search(r"min(?:imum)?\s*(?:deductible\s*)?(?:of\s*)?(?:US)?\$?\s*([\d,]+)", text, re.I)
    return m.group(1).replace(",", "") if m else None


def _extract_max(text: str) -> str | None:
    m = re.search(r"max(?:imum)?\s*(?:deductible\s*)?(?:of\s*)?(?:US)?\$?\s*([\d,]+)", text, re.I)
    return m.group(1).replace(",", "") if m else None


def _code_name(code: str) -> str:
    return {"EQ": "Earthquake", "WS": "Named Storm/Wind", "FL": "Flood", "FR": "AOP/Fire"}.get(code, code)
