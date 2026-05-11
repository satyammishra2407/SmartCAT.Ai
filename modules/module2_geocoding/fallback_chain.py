"""Six-level geocoding fallback chain (provider-agnostic labels)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any


class ResolutionLevel(IntEnum):
    BUILDING = 1
    PARCEL = 2
    STREET = 3
    POSTAL = 4
    CRESTA = 5  # placeholder: treat as postal/zone centroid when no CRESTA DB
    CITY = 6


@dataclass
class GeocodeHit:
    lat: float
    lon: float
    resolution: ResolutionLevel
    provider: str
    raw: dict[str, Any]


def google_location_type_to_level(location_type: str | None) -> ResolutionLevel:
    """Map Google Geocoding API geometry.location_type to resolution hierarchy."""
    if not location_type:
        return ResolutionLevel.POSTAL
    lt = location_type.upper()
    if lt == "ROOFTOP":
        return ResolutionLevel.BUILDING
    if lt == "RANGE_INTERPOLATED":
        return ResolutionLevel.STREET
    if lt == "GEOMETRIC_CENTER":
        return ResolutionLevel.PARCEL
    if lt == "APPROXIMATE":
        return ResolutionLevel.POSTAL
    return ResolutionLevel.POSTAL


def nominatim_importance_to_level(importance: float, query_tokens: int) -> ResolutionLevel:
    """Heuristic for OSM Nominatim (no standard footprint flag)."""
    if importance >= 0.7 and query_tokens >= 3:
        return ResolutionLevel.STREET
    if importance >= 0.5:
        return ResolutionLevel.POSTAL
    if importance >= 0.35:
        return ResolutionLevel.POSTAL
    return ResolutionLevel.CITY
