"""Parse addresses into components using usaddress (US) and heuristics."""
from __future__ import annotations

import re
from typing import Any

import usaddress

from smartcat_logging import get_logger

logger = get_logger("module1.parser")


def parse_us_address(text: str) -> dict[str, Any]:
    """Parse US-oriented addresses with usaddress."""
    text = re.sub(r"\s+", " ", str(text).strip())
    if not text:
        return _empty_components()

    try:
        tagged, _ = usaddress.tag(text)
    except usaddress.RepeatedLabelError:
        logger.warning("usaddress RepeatedLabelError for: %s", text[:80])
        return _heuristic_parse(text)

    house_number = tagged.get("AddressNumber", "") or tagged.get("OccupancyIdentifier", "")
    street = " ".join(
        filter(
            None,
            [
                tagged.get("StreetNamePreDirectional"),
                tagged.get("StreetNamePreType"),
                tagged.get("StreetName"),
                tagged.get("StreetNamePostType"),
                tagged.get("StreetNamePostDirectional"),
            ],
        )
    ).strip()

    if not street:
        street = tagged.get("StreetName") or text

    city = tagged.get("PlaceName", "") or ""
    state = tagged.get("StateName", "") or tagged.get("StateNameAbbreviation", "") or ""
    postal = tagged.get("ZipCode", "") or tagged.get("ZipPlus4", "") or ""
    if postal and "-" not in postal and len(postal) > 5 and postal[:5].isdigit():
        postal = postal[:5] + "-" + postal[5:]

    country = tagged.get("CountryName", "") or "US"

    return {
        "house_number": house_number.strip(),
        "street": street.strip(),
        "city": city.strip(),
        "state": state.strip(),
        "postal_code": postal.strip(),
        "country": country.strip() or "US",
        "raw": text,
    }


def _empty_components() -> dict[str, Any]:
    return {
        "house_number": "",
        "street": "",
        "city": "",
        "state": "",
        "postal_code": "",
        "country": "",
        "raw": "",
    }


def _heuristic_parse(text: str) -> dict[str, Any]:
    """Very light fallback: split by commas."""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    out = _empty_components()
    out["raw"] = text
    if len(parts) >= 1:
        first = parts[0].split(maxsplit=1)
        if first and first[0].replace("-", "").isdigit():
            out["house_number"] = first[0]
            out["street"] = first[1] if len(first) > 1 else ""
        else:
            out["street"] = parts[0]
    if len(parts) >= 2:
        out["city"] = parts[1]
    if len(parts) >= 3:
        state_zip = parts[2]
        m = re.match(r"([A-Za-z]{2}|[A-Za-z.\s]+)\s+([\d\-A-Za-z]+)\s*$", state_zip)
        if m:
            out["state"] = m.group(1).strip()
            out["postal_code"] = m.group(2).strip()
        else:
            out["state"] = state_zip
    if len(parts) >= 4:
        out["country"] = parts[3]
    return out


def merge_components(house: str, street: str, city: str, state: str, postal: str, country: str) -> dict[str, Any]:
    """Normalize pre-split columns."""
    full_street = " ".join(filter(None, [str(house).strip(), str(street).strip()])).strip()
    return {
        "house_number": str(house).strip() if house else "",
        "street": full_street or str(street).strip(),
        "city": str(city).strip(),
        "state": str(state).strip(),
        "postal_code": str(postal).strip(),
        "country": str(country).strip() or "US",
        "raw": "",
    }
