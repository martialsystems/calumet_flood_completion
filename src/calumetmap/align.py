# Copyright (c) 2026 Martial Systems LLC
"""Warp helpers on the live NLCD 2021 template. Fixture grids are refused."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS

from calumetmap.config import (
    FIXTURE_COLS,
    FIXTURE_ROWS,
    NLCD_NODATA,
    TEMPLATE_CRS,
    TEMPLATE_KIND_NLCD,
)
from calumetmap.errors import GateError
from calumetmap.template import TemplateGrid, sha256_file


def require_live_template(template: TemplateGrid) -> TemplateGrid:
    if template.width <= FIXTURE_COLS and template.height <= FIXTURE_ROWS:
        raise GateError("live path refuses the fixture grid")
    if template.kind != TEMPLATE_KIND_NLCD:
        raise GateError("live path requires nlcd_2021 template")
    if template.crs != TEMPLATE_CRS:
        raise GateError("template CRS {0} != {1}".format(template.crs, TEMPLATE_CRS))
    return template


def template_fingerprint(template: TemplateGrid) -> dict:
    t = template.transform
    payload = (
        "{0}|{1}|{2}|{3},{4},{5},{6},{7},{8}".format(
            template.crs,
            template.width,
            template.height,
            t.a,
            t.b,
            t.c,
            t.d,
            t.e,
            t.f,
        )
    )
    return {
        "kind": template.kind,
        "crs": template.crs,
        "width": template.width,
        "height": template.height,
        "transform": [float(t.a), float(t.b), float(t.c), float(t.d), float(t.e), float(t.f)],
        "transform_sha256": hashlib.sha256(payload.encode("ascii")).hexdigest(),
        "raster_sha256": sha256_file(template.path) if template.path.is_file() else "",
    }


def template_bounds(template: TemplateGrid) -> tuple[float, float, float, float]:
    t = template.transform
    west = float(t.c)
    north = float(t.f)
    east = west + template.width * float(t.a)
    south = north + template.height * float(t.e)
    return west, south, east, north


def interior_mask(template: TemplateGrid) -> np.ndarray:
    require_live_template(template)
    with rasterio.open(template.path) as src:
        arr = src.read(1)
        nod = src.nodata
    if nod is None:
        nod = NLCD_NODATA
    return arr != nod


def write_aligned(
    dest: Path,
    template: TemplateGrid,
    data: np.ndarray,
    *,
    dtype: str,
    nodata,
) -> Path:
    require_live_template(template)
    if data.shape != (template.height, template.width):
        raise GateError(
            "aligned raster shape {0} != ({1}, {2})".format(
                data.shape, template.height, template.width
            )
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "height": template.height,
        "width": template.width,
        "count": 1,
        "dtype": dtype,
        "crs": CRS.from_epsg(template.crs),
        "transform": template.transform,
        "nodata": nodata,
        "compress": "lzw",
    }
    with rasterio.open(dest, "w", **profile) as dst:
        dst.write(np.asarray(data, dtype=dtype), 1)
    return dest
