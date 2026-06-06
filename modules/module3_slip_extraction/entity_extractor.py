"""Combine regex + table parsing into structured slip record."""
from __future__ import annotations

from typing import Any

from modules.module3_slip_extraction import pattern_library as pl
from modules.module3_slip_extraction.section_detector import split_sections
from modules.module3_slip_extraction.table_parser import (
    build_cat_peril_summary,
    parse_deductible_rows,
    parse_limit_rows,
    parse_waiting_periods,
)


def extract_from_text(text: str, source_file: str = "", extraction_method: str = "text") -> dict[str, Any]:
    sections = split_sections(text)
    blob = text if not sections.get("full") else sections.get("full", text)

    summary = _extract_summary(blob, source_file, extraction_method)
    limits = parse_limit_rows(blob, source_file)
    deductibles = parse_deductible_rows(blob, source_file)
    waiting = parse_waiting_periods(blob, source_file)

    # Regex sublimits not caught by table parser
    for m in pl.SUBLIMIT_PERIL.finditer(blob):
        peril = m.group(1).strip()
        val = m.group(2).strip()
        if not any(r.get("description", "").startswith(peril) for r in limits):
            limits.append(
                {
                    "source_file": source_file,
                    "row_type": "sublimit",
                    "description": peril,
                    "peril": peril,
                    "peril_code": _peril_code(peril),
                    "region": None,
                    "amount": pl.clean_money(val) if "excluded" not in val.lower() else None,
                    "currency": "USD",
                    "status": "excluded" if "excluded" in val.lower() else "active",
                    "basis": "occurrence",
                    "parent_peril": None,
                    "rms_field": "PARTOF",
                }
            )

    # Merge regex deductibles if table sparse
    if len(deductibles) < 2:
        deductibles.extend(_regex_deductibles(blob, source_file))

    if not waiting:
        m = pl.WAITING.search(blob)
        if m:
            amt = int(m.group(1))
            unit = m.group(2).lower()
            hours = amt * 24 if "day" in unit else amt
            waiting.append(
                {
                    "source_file": source_file,
                    "coverage": "General",
                    "hours": hours,
                    "days": round(hours / 24, 2) if hours >= 24 else None,
                    "raw": m.group(0),
                }
            )

    summary["confidence_score"] = _confidence(summary, limits, deductibles, extraction_method)

    return {
        **summary,
        "limits_sublimits": limits,
        "deductibles": deductibles,
        "waiting_periods": waiting,
        "cat_peril_summary": build_cat_peril_summary(limits, deductibles),
    }


def _extract_summary(blob: str, source_file: str, extraction_method: str) -> dict[str, Any]:
    out: dict[str, Any] = {
        "source_file": source_file,
        "named_insured": None,
        "effective_date": None,
        "expiration_date": None,
        "policy_period_raw": None,
        "tiv": None,
        "tiv_currency": "USD",
        "tiv_notes": None,
        "limit_of_liability": None,
        "blanket_limit": None,
        "aggregate_limit": None,
        "part_of": None,
        "participation_pct": None,
        "coinsurance_pct": None,
        "excess_of": None,
        "sir": None,
        "blanket_deductible": None,
        "min_deductible": None,
        "max_deductible": None,
        "policy_form": None,
        "loss_history": None,
        "extraction_method": extraction_method,
    }

    for pat in pl.TIV_PATTERNS:
        m = pat.search(blob)
        if m:
            out["tiv"] = pl.clean_money(m.group(1))
            if m.lastindex and m.lastindex >= 2 and m.group(2):
                out["tiv_currency"] = m.group(2).upper()
            break

    m = pl.NAMED_INSURED.search(blob)
    if m:
        out["named_insured"] = m.group(1).strip()[:200]

    m = pl.EFFECTIVE_DATE.search(blob)
    if m:
        out["effective_date"] = m.group(1)
    m = pl.EXPIRATION_DATE.search(blob)
    if m:
        out["expiration_date"] = m.group(1)
    m = pl.POLICY_PERIOD.search(blob)
    if m:
        out["policy_period_raw"] = m.group(1).strip()

    for pat, key in (
        (pl.LIMIT_PROGRAM, "limit_of_liability"),
        (pl.LIMIT_OCC, "limit_of_liability"),
        (pl.BLANKET_LIMIT, "blanket_limit"),
        (pl.LIMIT_AGG, "aggregate_limit"),
    ):
        m = pat.search(blob)
        if m and not out.get(key):
            out[key] = pl.clean_money(m.group(1))

    # From limit table rows
    for line in blob.splitlines():
        pair_line = line.strip()
        if "limit of liability" in pair_line.lower():
            amt = pl.parse_money_from_text(pair_line)
            if amt and not out["limit_of_liability"]:
                out["limit_of_liability"] = amt

    m = pl.COINSURANCE.search(blob)
    if m:
        out["coinsurance_pct"] = float(m.group(1))
        out["participation_pct"] = float(m.group(1))

    m = pl.PART_OF.search(blob)
    if m:
        out["part_of"] = pl.clean_money(m.group(1)) or m.group(1)

    m = pl.EXCESS_OF.search(blob)
    if m:
        out["excess_of"] = pl.clean_money(m.group(1)) or m.group(1)

    m = pl.SIR.search(blob)
    if m:
        out["sir"] = pl.clean_money(m.group(1))

    m = pl.BLANKET_DED.search(blob)
    if m:
        out["blanket_deductible"] = pl.clean_money(m.group(1))
    else:
        m = pl.DEDUCT_FIXED.search(blob)
        if m:
            out["blanket_deductible"] = pl.clean_money(m.group(1))

    m = pl.MIN_DED.search(blob)
    if m:
        out["min_deductible"] = pl.clean_money(m.group(1))
    m = pl.MAX_DED.search(blob)
    if m:
        out["max_deductible"] = pl.clean_money(m.group(1))

    m = pl.POLICY_FORM.search(blob)
    if m:
        out["policy_form"] = m.group(1).strip()[:120]

    m = pl.LOSS_HISTORY.search(blob)
    if m:
        out["loss_history"] = m.group(1).strip()[:200]

    m = pl.TIV_NOTES.search(blob)
    if m:
        out["tiv_notes"] = m.group(1).strip()

    return out


def _regex_deductibles(blob: str, source_file: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    m = pl.DEDUCT_PCT.search(blob)
    if m:
        entry: dict[str, Any] = {
            "source_file": source_file,
            "peril": "General",
            "peril_code": "FR",
            "region": None,
            "hazard_zone": None,
            "coverage_type": "combined",
            "deductible_type": "hybrid",
            "amount": None,
            "pct": float(m.group(1)),
            "min_amount": pl.clean_money(m.group(2)) if m.lastindex and m.lastindex >= 2 else None,
            "max_amount": pl.clean_money(m.group(3)) if m.lastindex and m.lastindex >= 3 else None,
            "basis": "per_occurrence",
            "waiting_hours": None,
            "notes": m.group(0)[:200],
            "rms_field": "BLANDEDAMT",
        }
        rows.append(entry)
    m = pl.DEDUCT_FIXED.search(blob)
    if m:
        rows.append(
            {
                "source_file": source_file,
                "peril": "General",
                "peril_code": "FR",
                "region": None,
                "hazard_zone": None,
                "coverage_type": "combined",
                "deductible_type": "monetary",
                "amount": pl.clean_money(m.group(1)),
                "pct": None,
                "min_amount": None,
                "max_amount": None,
                "basis": "per_occurrence",
                "waiting_hours": None,
                "notes": None,
                "rms_field": "BLANDEDAMT",
            }
        )
    return rows


def _peril_code(peril: str) -> str | None:
    lower = peril.lower()
    if "earth" in lower or "seismic" in lower:
        return "EQ"
    if "flood" in lower:
        return "FL"
    if "storm" in lower or "wind" in lower:
        return "WS"
    if "fire" in lower or "wild" in lower:
        return "WF"
    return None


def _confidence(summary: dict, limits: list, deductibles: list, method: str) -> int:
    score = 0
    if summary.get("tiv"):
        score += 30
    if summary.get("limit_of_liability") or summary.get("blanket_limit"):
        score += 20
    if len(limits) >= 3:
        score += 15
    elif len(limits) >= 1:
        score += 8
    if len(deductibles) >= 2:
        score += 15
    elif len(deductibles) >= 1:
        score += 8
    if summary.get("effective_date"):
        score += 10
    if method in ("text_pdf", "docx"):
        score += 10
    return min(score, 100)
