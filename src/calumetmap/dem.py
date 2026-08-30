# Copyright (c) 2026 Martial Systems LLC
"""USGS 3DEP elevation, tiled onto the live Calumet template."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from rasterio.io import MemoryFile

from calumetmap.align import interior_mask, require_live_template, template_bounds, write_aligned
from calumetmap.config import DEM_IMAGE_URL, DEM_NODATA, DEM_TILE_PX, TEMPLATE_CRS
from calumetmap.errors import FetchError, GateError
from calumetmap.fetch import GetBytes, default_get_bytes, iter_tiles
from calumetmap.template import TemplateGrid


def dem_export_url(
    *,
    west: float,
    south: float,
    east: float,
    north: float,
    width: int,
    height: int,
) -> str:
    return (
        "{0}?bbox={1},{2},{3},{4}&bboxSR={5}&imageSR={5}"
        "&size={6},{7}&format=tiff&pixelType=F32"
        "&interpolation=RSP_BilinearInterpolation&f=image"
    ).format(DEM_IMAGE_URL, west, south, east, north, TEMPLATE_CRS, width, height)


def fetch_dem(
    template: TemplateGrid,
    dest: Path,
    *,
    get_bytes: GetBytes | None = None,
    tile_px: int = DEM_TILE_PX,
) -> dict:
    require_live_template(template)
    getter = get_bytes or default_get_bytes
    west, south, east, north = template_bounds(template)
    dest_arr = np.full(
        (template.height, template.width), DEM_NODATA, dtype=np.float32
    )
    n_tiles = 0
    for tw, ts, te, tn, w, h in iter_tiles(
        west, south, east, north, tile_px=tile_px
    ):
        url = dem_export_url(west=tw, south=ts, east=te, north=tn, width=w, height=h)
        payload = getter(url)
        if payload[:4] not in (b"II*\x00", b"MM\x00*"):
            raise FetchError("3DEP export is not TIFF: {0}".format(url[:120]))
        with MemoryFile(payload) as mem, mem.open() as src:
            tile = src.read(1)
            if tile.shape != (h, w):
                raise GateError("3DEP tile shape {0} != {1}".format(tile.shape, (h, w)))
            col0 = int(round((tw - west) / abs(template.transform.a)))
            row0 = int(round((north - tn) / abs(template.transform.e)))
            dest_arr[row0 : row0 + h, col0 : col0 + w] = tile
        n_tiles += 1
    inside = interior_mask(template)
    dest_arr[~inside] = DEM_NODATA
    if not np.isfinite(dest_arr[inside]).any():
        raise GateError("DEM has no finite cells inside the HUC")
    write_aligned(dest, template, dest_arr, dtype="float32", nodata=DEM_NODATA)
    valid = dest_arr[inside]
    valid = valid[np.isfinite(valid) & (valid != DEM_NODATA)]
    return {
        "n_tiles": n_tiles,
        "dem_min": float(valid.min()) if valid.size else None,
        "dem_max": float(valid.max()) if valid.size else None,
        "path": str(dest),
    }
