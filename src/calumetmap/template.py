# Copyright (c) 2026 Martial Systems LLC
"""30 m EPSG:5070 template raster. Fixture writer and live-grid check."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_origin

from calumetmap.config import (
    FIXTURE_COLS,
    FIXTURE_NORTH,
    FIXTURE_ROWS,
    FIXTURE_WEST,
    TEMPLATE_CRS,
    TEMPLATE_KIND_FIXTURE,
    TEMPLATE_KIND_NLCD,
    TEMPLATE_RES_M,
)
from calumetmap.crs import epsg_from_rasterio, require_epsg
from calumetmap.errors import GateError


@dataclass(frozen=True)
class TemplateGrid:
    path: Path
    crs: int
    res_m: float
    width: int
    height: int
    transform: rasterio.Affine
    kind: str


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def write_fixture_template(path: Path) -> TemplateGrid:
    path.parent.mkdir(parents=True, exist_ok=True)
    transform = from_origin(FIXTURE_WEST, FIXTURE_NORTH, TEMPLATE_RES_M, TEMPLATE_RES_M)
    data = np.zeros((FIXTURE_ROWS, FIXTURE_COLS), dtype=np.uint8)
    profile = {
        "driver": "GTiff",
        "height": FIXTURE_ROWS,
        "width": FIXTURE_COLS,
        "count": 1,
        "dtype": "uint8",
        "crs": CRS.from_epsg(TEMPLATE_CRS),
        "transform": transform,
        "nodata": 255,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)
    return inspect_template(path, kind=TEMPLATE_KIND_FIXTURE)


def inspect_template(path: Path, *, kind: str) -> TemplateGrid:
    if not path.is_file():
        raise GateError("missing template: {0}".format(path))
    with rasterio.open(path) as src:
        epsg = require_epsg(epsg_from_rasterio(src.crs), expected=TEMPLATE_CRS)
        res_x = abs(src.transform.a)
        res_y = abs(src.transform.e)
        if abs(res_x - TEMPLATE_RES_M) > 1e-6 or abs(res_y - TEMPLATE_RES_M) > 1e-6:
            raise GateError(
                "template resolution {0}x{1} m != {2} m".format(res_x, res_y, TEMPLATE_RES_M)
            )
        if src.width < 2 or src.height < 2:
            raise GateError("template too small: {0}x{1}".format(src.width, src.height))
        return TemplateGrid(
            path=path,
            crs=epsg,
            res_m=TEMPLATE_RES_M,
            width=src.width,
            height=src.height,
            transform=src.transform,
            kind=kind,
        )


def refuse_nlcd_kind_on_fixture(template: TemplateGrid, *, kind: str) -> None:
    if kind == TEMPLATE_KIND_NLCD and (
        template.width <= FIXTURE_COLS and template.height <= FIXTURE_ROWS
    ):
        raise GateError("nlcd_2021 template looks like the fixture grid")
