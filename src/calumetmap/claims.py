# Copyright (c) 2026 Martial Systems LLC
"""Fail closed: P is map-completion, not a 100-year. No Indy plant table."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from calumetmap.config import INDY_PLANT_NAMES
from calumetmap.errors import ClaimBanError

_BANS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "casualty_count",
        re.compile(
            r"\b(deaths?|fatalit(?:y|ies)|casualt(?:y|ies)|killed|injuries)\b",
            re.I,
        ),
    ),
    (
        "climate_attribution",
        re.compile(
            r"\b(cmip\d*|downscal(?:e|ed|ing)|gcm)\b|"
            r"climate(?:\s+change)?\s+(?:made|caused|attributed)",
            re.I,
        ),
    ),
    ("tornado_count", re.compile(r"\btornado(?:es)?\s+counts?\b", re.I)),
    (
        "population_at_risk",
        re.compile(
            r"\b(lives\s+at\s+risk|people\s+at\s+risk|population\s+at\s+risk)\b",
            re.I,
        ),
    ),
    (
        "p_as_100yr",
        re.compile(
            r"\b100-year\s+exceedance\b|"
            r"\bprobability of (?:a )?100-year\b|"
            r"\bP\(flood\) is the 100-year\b",
            re.I,
        ),
    ),
    ("unmapped_risk", re.compile(r"\bunmapped risk\b", re.I)),
)


def scan_text(text: str) -> list[str]:
    hits: list[str] = []
    blob = text or ""
    for name, pat in _BANS:
        if pat.search(blob):
            hits.append(name)
    for plant in INDY_PLANT_NAMES:
        if plant.lower() in blob.lower():
            hits.append("indy_plant_copy")
            break
    if "\u2014" in blob:
        hits.append("em_dash")
    return hits


def scan_obj(obj: object) -> list[str]:
    return scan_text(json.dumps(obj, default=str))


def require_clean(text: str, *, source: str) -> None:
    hits = scan_text(text)
    if hits:
        raise ClaimBanError("{0}: banned claims {1}".format(source, hits))


def require_paths_clean(paths: Iterable[Path]) -> None:
    for path in paths:
        if path.is_file():
            require_clean(path.read_text(encoding="utf-8"), source=str(path))
