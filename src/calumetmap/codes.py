# Copyright (c) 2026 Martial Systems LLC
"""FIRM zone_class codebook. Unshaded X is Zone X, not unmapped."""

from __future__ import annotations

ZONE_UNMAPPED = 0
ZONE_SFHA = 1
ZONE_FLOODWAY = 2
ZONE_SHADED_X = 3
ZONE_UNSHADED_X = 4
ZONE_D = 5
ZONE_OTHER = 6

ZONE_CLASS_NAME = {
    ZONE_UNMAPPED: "unmapped",
    ZONE_SFHA: "sfha",
    ZONE_FLOODWAY: "floodway",
    ZONE_SHADED_X: "shaded_x",
    ZONE_UNSHADED_X: "unshaded_x",
    ZONE_D: "D",
    ZONE_OTHER: "other",
}
ZONE_CLASS_CODE = {name: code for code, name in ZONE_CLASS_NAME.items()}

D1_ZONE_CLASS = "unshaded_x"


def d1_eligible(zone_class: str) -> bool:
    return zone_class == D1_ZONE_CLASS

_SFHA_ZONES = frozenset({"A", "AE", "AH", "AO", "AR", "A99", "V", "VE"})
_UNMAPPED_ZONES = frozenset({"", "OPEN WATER", "AREA NOT INCLUDED"})


def _sfha_true(sfha_tf: object) -> bool:
    token = str(sfha_tf or "").strip().upper()
    return token in {"T", "TRUE", "1", "YES"}


def classify_firm_zone(
    fld_zone: object,
    zone_subty: object = "",
    sfha_tf: object = "",
) -> tuple[int, str]:
    """Return (zone_code, zone_class) from NFHL S_FLD_HAZ_AR attributes.

    Unshaded X is FLD_ZONE X with empty ZONE_SUBTY or AREA OF MINIMAL
    FLOOD HAZARD. Shaded X is 0.2 PCT ANNUAL CHANCE FLOOD HAZARD.
    Floodway is SFHA; the binary sfha band must include those cells.
    """
    zone = str(fld_zone or "").strip().upper()
    sub = str(zone_subty or "").strip().upper()
    sfha = _sfha_true(sfha_tf)
    if "FLOODWAY" in sub and (sfha or zone in _SFHA_ZONES):
        return ZONE_FLOODWAY, "floodway"
    if sfha or zone in _SFHA_ZONES:
        return ZONE_SFHA, "sfha"
    if zone == "D":
        return ZONE_D, "D"
    if zone == "X" or "MINIMAL FLOOD" in sub or "0.2" in sub:
        if "0.2" in sub or "SHADED" in sub:
            return ZONE_SHADED_X, "shaded_x"
        return ZONE_UNSHADED_X, "unshaded_x"
    if zone in _UNMAPPED_ZONES or "NOT INCLUDED" in zone:
        return ZONE_UNMAPPED, "unmapped"
    return ZONE_OTHER, "other"
