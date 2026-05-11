"""Combine regex extraction into structured dict."""
from __future__ import annotations

from typing import Any

from modules.module3_slip_extraction import pattern_library as pl
from modules.module3_slip_extraction.section_detector import split_sections


def extract_from_text(text: str) -> dict[str, Any]:
    sections = split_sections(text)
    blob = text if not sections.get("full") else sections.get("full", text)

    out: dict[str, Any] = {
        "tiv": None,
        "tiv_currency": "USD",
        "limits_occurrence": None,
        "limits_aggregate": None,
        "sublimits": [],
        "deductibles": [],
        "coinsurance_pct": None,
        "sir": None,
        "waiting_period": None,
        "policy_form": None,
    }

    for pat in pl.TIV_PATTERNS:
        m = pat.search(blob)
        if m:
            out["tiv"] = pl.clean_money(m.group(1))
            if m.lastindex and m.lastindex >= 2 and m.group(2):
                out["tiv_currency"] = m.group(2).upper()
            break

    m = pl.LIMIT_OCC.search(blob)
    if m:
        out["limits_occurrence"] = pl.clean_money(m.group(1))
    m = pl.LIMIT_AGG.search(blob)
    if m:
        out["limits_aggregate"] = pl.clean_money(m.group(1))

    for m in pl.SUBLIMIT_PERIL.finditer(blob):
        peril = m.group(1)
        val = m.group(2)
        out["sublimits"].append({"peril": peril, "amount_or_status": pl.clean_money(val) or val})

    m = pl.DEDUCT_PCT.search(blob)
    if m:
        entry = {"type": "pct_of_tiv", "pct": m.group(1)}
        if m.group(2):
            entry["min"] = pl.clean_money(m.group(2))
        if m.group(3):
            entry["max"] = pl.clean_money(m.group(3))
        out["deductibles"].append(entry)
    m = pl.DEDUCT_FIXED.search(blob)
    if m and not out["deductibles"]:
        out["deductibles"].append({"type": "fixed", "amount": pl.clean_money(m.group(1))})

    m = pl.COINSURANCE.search(blob)
    if m:
        out["coinsurance_pct"] = float(m.group(1))
    m = pl.SIR.search(blob)
    if m:
        out["sir"] = pl.clean_money(m.group(1))
    m = pl.WAITING.search(blob)
    if m:
        amt = m.group(1)
        unit = m.group(2).lower()
        hours = int(amt) * (24 if "day" in unit else 1)
        out["waiting_period"] = {"hours": hours, "raw": f"{amt} {unit}"}
    m = pl.POLICY_FORM.search(blob)
    if m:
        out["policy_form"] = m.group(1).strip()[:120]

    return out
