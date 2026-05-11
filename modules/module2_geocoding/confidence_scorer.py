"""Map resolution level to 0–100 confidence."""
from __future__ import annotations

from modules.module2_geocoding.fallback_chain import ResolutionLevel

LEVEL_SCORE = {
    ResolutionLevel.BUILDING: 95,
    ResolutionLevel.PARCEL: 82,
    ResolutionLevel.STREET: 70,
    ResolutionLevel.POSTAL: 50,
    ResolutionLevel.CRESTA: 42,
    ResolutionLevel.CITY: 25,
}


def score_for_level(level: ResolutionLevel, provider_primary: bool = True) -> int:
    base = LEVEL_SCORE.get(level, 30)
    if not provider_primary:
        base = max(0, base - 8)
    return min(100, base)
