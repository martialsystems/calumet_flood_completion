# Copyright (c) 2026 Martial Systems LLC
"""Load a HUC polygon. Refuse empty geometry and the Upper White HUC."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from calumetmap.config import EXPECTED_AREA_SQKM, HUC8, PARENT_HUC8, STATE_CODE, VECTOR_CRS
from calumetmap.crs import require_epsg
from calumetmap.errors import CrsMissingError, EmptyHucError, GateError


@dataclass(frozen=True)
class HucLayer:
    geom: BaseGeometry
    huc8: str
    crs: int
    n_features: int
    name: str = ""
    states: str = ""
    areasqkm: float | None = None


def _crs_from_geojson(doc: dict[str, Any]) -> int | None:
    crs = doc.get("crs")
    if isinstance(crs, dict):
        props = crs.get("properties") or {}
        name = str(props.get("name") or "")
        if "4269" in name:
            return 4269
        if "5070" in name:
            return 5070
        if name.upper().startswith("EPSG:"):
            try:
                return int(name.split(":", 1)[1])
            except ValueError:
                return None
        wkid = props.get("wkid")
        if wkid is not None:
            try:
                return int(wkid)
            except (TypeError, ValueError):
                return None
    return None


def _huc_code(props: dict[str, Any]) -> str:
    for key in ("huc8", "HUC8", "huc", "HUC"):
        val = props.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def _optional_area(props: dict[str, Any]) -> float | None:
    raw = props.get("areasqkm")
    if raw is None:
        raw = props.get("AREASQKM")
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise GateError("HUC areasqkm not a number: {0!r}".format(raw)) from exc


def load_huc(
    path: Path,
    *,
    wkid: int | None = None,
    expected_huc: str = HUC8,
) -> HucLayer:
    doc = json.loads(path.read_text(encoding="utf-8"))
    file_crs = _crs_from_geojson(doc)
    crs = require_epsg(
        file_crs if file_crs is not None else wkid,
        expected=VECTOR_CRS,
    )
    features = doc.get("features") or []
    geoms: list[BaseGeometry] = []
    codes: list[str] = []
    kept_props: list[dict[str, Any]] = []
    for feat in features:
        geom_doc = feat.get("geometry")
        if not geom_doc:
            continue
        geom = shape(geom_doc)
        if geom.is_empty:
            continue
        props = feat.get("properties") or {}
        geoms.append(geom)
        codes.append(_huc_code(props))
        kept_props.append(props)
    if not geoms:
        raise EmptyHucError("no HUC polygons in {0}".format(path))
    merged = geoms[0]
    for extra in geoms[1:]:
        merged = merged.union(extra)
    if merged.is_empty:
        raise EmptyHucError("empty union in {0}".format(path))
    code = next((c for c in codes if c), expected_huc)
    if code == PARENT_HUC8:
        raise GateError("refuse Upper White HUC {0} in the Calumet tree".format(PARENT_HUC8))
    if code != expected_huc:
        raise EmptyHucError("HUC {0!r} != {1!r}".format(code, expected_huc))
    first_props = kept_props[0] if kept_props else {}
    name = str(first_props.get("name") or first_props.get("NAME") or "")
    states = str(first_props.get("states") or first_props.get("STATES") or "")
    area = _optional_area(first_props)
    if states and STATE_CODE not in states.upper():
        raise GateError("HUC states={0!r} missing {1}".format(states, STATE_CODE))
    if area is not None:
        lo, hi = EXPECTED_AREA_SQKM
        if not (lo <= area <= hi):
            raise GateError("HUC area_sqkm={0} outside {1}".format(area, EXPECTED_AREA_SQKM))
    return HucLayer(
        geom=merged,
        huc8=code,
        crs=crs,
        n_features=len(geoms),
        name=name,
        states=states,
        areasqkm=area,
    )


def require_huc_crs(wkid: int | None, *, expected: int = VECTOR_CRS) -> int:
    if wkid is None:
        raise CrsMissingError("HUC layer has no CRS")
    return require_epsg(wkid, expected=expected)
