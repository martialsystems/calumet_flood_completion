# Copyright (c) 2026 Martial Systems LLC
"""Stage B: slope floor, D8 HAND, distances on this HUC. No Nora warp. No P."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import rasterio

from calumetmap.align import interior_mask, require_live_template, template_fingerprint, write_aligned
from calumetmap.config import (
    DEM_NODATA,
    DIST_NODATA,
    FIRM_LIVE_MIN_HEIGHT,
    FIRM_LIVE_MIN_WIDTH,
    HAND_NODATA_RULE,
    HUC8,
    HYDRO_BURN_M,
    HYDRO_NODATA,
    LOCKED_TRANSFORM_SHA256,
    NORA_HAND_MARKERS,
    SLOPE_FLOOR_RAD,
    STAGE_B_BANDS,
    TEMPLATE_KIND_NLCD,
    TEMPLATE_RES_M,
    WBD_LIVE_AREASQKM,
)
from calumetmap.dem import fetch_dem
from calumetmap.errors import GateError
from calumetmap.huc import load_huc
from calumetmap.hydro import (
    burn_dem,
    d8_flowdir,
    euclidean_distance_m,
    flow_accumulation,
    hand_along_flow,
    priority_flood_fill,
    require_finite_twi,
    slope_radians,
    topographic_wetness,
)
from calumetmap.nhd import (
    features_to_mask,
    fetch_area_streamriver,
    fetch_flowlines,
    fetch_waterbodies,
    ftype_counts,
)
from calumetmap.report import build_stage_b_report, write_report
from calumetmap.template import inspect_template

try:
    from calumetforge.gate import require_claims, require_huc, require_stage
except ImportError:  # pragma: no cover

    def require_claims(**kwargs):
        del kwargs

    def require_huc(**kwargs):
        del kwargs

    def require_stage(**kwargs):
        del kwargs


def refuse_nora_hand_copy(paths: Iterable[Path | str]) -> None:
    for path in paths:
        blob = str(path).lower()
        for marker in NORA_HAND_MARKERS:
            if marker.lower() in blob:
                raise GateError("do not warp Nora HAND onto this HUC: {0}".format(path))


def _load_a_report(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GateError("Stage A report missing: {0}".format(path))
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("stage") != "A" or obj.get("gate") != "pass":
        raise GateError("Stage A report is not a passing Stage A artifact")
    if not obj.get("firm_unshaded_x_ok"):
        raise GateError("Stage B requires firm_unshaded_x_ok")
    if obj.get("huc8") != HUC8:
        raise GateError("Stage A report HUC {0!r} != {1!r}".format(obj.get("huc8"), HUC8))
    return obj


def _paint(values: np.ndarray, valid: np.ndarray, nodata: float) -> np.ndarray:
    out = np.full(values.shape, nodata, dtype=np.float32)
    finite = valid & np.isfinite(values)
    out[finite] = values[finite].astype(np.float32)
    return out


def _band_meta(name: str, path: Path, nodata: float, units: str) -> dict[str, Any]:
    return {
        "name": name,
        "path": str(path),
        "nodata": nodata,
        "units": units,
        "dtype": "float32",
    }


def run_stage_b(
    *,
    huc_path: Path,
    template_path: Path,
    interim_dir: Path,
    out_dir: Path,
    stage_a_report_path: Path,
    get_json=None,
    get_bytes=None,
    flowline_features: list | None = None,
    waterbody_features: list | None = None,
    area_features: list | None = None,
) -> dict:
    require_claims()
    refuse_nora_hand_copy(
        [huc_path, template_path, interim_dir, out_dir, stage_a_report_path]
    )
    a_report = _load_a_report(stage_a_report_path)
    huc = load_huc(huc_path)
    require_huc(huc8=huc.huc8, parent_huc=False)
    template = inspect_template(template_path, kind=TEMPLATE_KIND_NLCD)
    require_live_template(template)
    fp = template_fingerprint(template)
    live = template.width >= FIRM_LIVE_MIN_WIDTH and template.height >= FIRM_LIVE_MIN_HEIGHT
    a_fp = (a_report.get("template_fingerprint") or {}).get("transform_sha256")
    if a_fp and a_fp != fp["transform_sha256"]:
        raise GateError("Stage B template transform does not match Stage A")
    if a_fp == LOCKED_TRANSFORM_SHA256 and fp["transform_sha256"] != LOCKED_TRANSFORM_SHA256:
        raise GateError(
            "template transform {0} != locked {1}".format(
                fp["transform_sha256"], LOCKED_TRANSFORM_SHA256
            )
        )
    require_stage(
        current_stage="A",
        target_stage="B",
        template_kind=TEMPLATE_KIND_NLCD,
        firm_unshaded_x_ok=True,
        stage_a_report=True,
        thread_id="stage_b",
    )

    interim_dir.mkdir(parents=True, exist_ok=True)
    dem_path = interim_dir / "dem.tif"
    if dem_path.is_file():
        dem_info = {"path": str(dem_path), "skipped_existing": True}
    else:
        dem_info = fetch_dem(template, dem_path, get_bytes=get_bytes)
    inside = interior_mask(template)
    with rasterio.open(dem_path) as src:
        if tuple(src.transform)[:6] != tuple(template.transform)[:6]:
            raise GateError("DEM transform does not match the live template")
        dem = src.read(1).astype(np.float64)
        dem_nod = src.nodata if src.nodata is not None else DEM_NODATA
    dem_valid = inside & np.isfinite(dem) & (dem != dem_nod)
    if not dem_valid.any():
        raise GateError("DEM has no finite interior cells")

    if flowline_features is None:
        flowline_features = fetch_flowlines(huc, get_json)
    if waterbody_features is None:
        waterbody_features = fetch_waterbodies(huc, get_json)
    if area_features is None:
        area_features = fetch_area_streamriver(huc, get_json)

    flow_mask = features_to_mask(flowline_features, template).astype(bool)
    water_mask = features_to_mask(waterbody_features, template).astype(bool)
    area_mask = features_to_mask(area_features or [], template).astype(bool)
    stream_mask = (flow_mask | water_mask | area_mask) & dem_valid
    if not stream_mask.any():
        raise GateError("burn mask is empty; NHD flowline/waterbody raster is empty")

    if live:
        print("Stage B: slope, burn, fill, D8, accumulation", flush=True)
    slope = slope_radians(dem, dem_valid, TEMPLATE_RES_M)
    burned = burn_dem(dem, stream_mask, depth_m=HYDRO_BURN_M, valid=dem_valid)
    filled = priority_flood_fill(burned, dem_valid, seed_mask=stream_mask)
    flowdir = d8_flowdir(filled, dem_valid, TEMPLATE_RES_M)
    acc = flow_accumulation(flowdir, dem_valid)
    twi, n_floor = topographic_wetness(
        acc, slope, TEMPLATE_RES_M, floor_rad=SLOPE_FLOOR_RAD, valid=dem_valid
    )
    require_finite_twi(twi, dem_valid)
    hand = hand_along_flow(dem, flowdir, stream_mask, dem_valid)
    dist_fl = euclidean_distance_m(flow_mask & inside, TEMPLATE_RES_M)
    if (water_mask & inside).any():
        dist_wb = euclidean_distance_m(water_mask & inside, TEMPLATE_RES_M)
    else:
        dist_wb = np.full(inside.shape, DIST_NODATA, dtype=np.float64)
        dist_wb[inside] = np.nan

    slope_path = interim_dir / "slope.tif"
    twi_path = interim_dir / "twi.tif"
    hand_path = interim_dir / "hand.tif"
    dfl_path = interim_dir / "dist_flowline.tif"
    dwb_path = interim_dir / "dist_waterbody.tif"
    write_aligned(slope_path, template, _paint(slope, dem_valid, HYDRO_NODATA), dtype="float32", nodata=HYDRO_NODATA)
    write_aligned(twi_path, template, _paint(twi, dem_valid, HYDRO_NODATA), dtype="float32", nodata=HYDRO_NODATA)
    write_aligned(hand_path, template, _paint(hand, dem_valid, HYDRO_NODATA), dtype="float32", nodata=HYDRO_NODATA)
    write_aligned(
        dfl_path,
        template,
        _paint(dist_fl, inside, DIST_NODATA),
        dtype="float32",
        nodata=DIST_NODATA,
    )
    write_aligned(
        dwb_path,
        template,
        _paint(dist_wb, inside, DIST_NODATA),
        dtype="float32",
        nodata=DIST_NODATA,
    )
    bands = {
        "slope": slope_path,
        "twi": twi_path,
        "hand": hand_path,
        "dist_flowline": dfl_path,
        "dist_waterbody": dwb_path,
    }
    missing = [name for name in STAGE_B_BANDS if name not in bands]
    if missing:
        raise GateError("Stage B bands missing {0}".format(missing))

    n_hand_undef = int((dem_valid & ~np.isfinite(hand)).sum())
    n_interior = int(inside.sum())
    if live and fp["transform_sha256"] == LOCKED_TRANSFORM_SHA256:
        area_km2 = n_interior * (TEMPLATE_RES_M ** 2) / 1.0e6
        if abs(area_km2 - WBD_LIVE_AREASQKM) > 2.0:
            raise GateError(
                "interior area {0:.2f} km2 != WBD pin {1}".format(area_km2, WBD_LIVE_AREASQKM)
            )

    extra = {
        "template_fingerprint": fp,
        "firm_unshaded_x_ok": True,
        "n_interior": n_interior,
        "n_dem_valid": int(dem_valid.sum()),
        "n_slope_floor": n_floor,
        "slope_floor_rad": SLOPE_FLOOR_RAD,
        "n_stream_cells": int(stream_mask.sum()),
        "n_flowline_cells": int((flow_mask & inside).sum()),
        "n_waterbody_cells": int((water_mask & inside).sum()),
        "n_hand_undefined": n_hand_undef,
        "hand_nodata_rule": HAND_NODATA_RULE,
        "hand_nodata_filled_with_zero": False,
        "twi_finite_on_dem_valid": True,
        "hand_is_flow_path": True,
        "hydro_burn_m": HYDRO_BURN_M,
        "n_flowline_features": len(flowline_features),
        "n_waterbody_features": len(waterbody_features),
        "n_area_460_features": len(area_features or []),
        "flowline_ftype_counts": ftype_counts(flowline_features),
        "dem": dem_info,
        "bands": [
            _band_meta("slope", slope_path, HYDRO_NODATA, "rad"),
            _band_meta("twi", twi_path, HYDRO_NODATA, "ln(m)"),
            _band_meta("hand", hand_path, HYDRO_NODATA, "m"),
            _band_meta("dist_flowline", dfl_path, DIST_NODATA, "m"),
            _band_meta("dist_waterbody", dwb_path, DIST_NODATA, "m"),
        ],
        "stage_c_started": False,
        "nora_hand_copied": False,
    }
    report = build_stage_b_report(huc, template, extra=extra)
    require_stage(
        current_stage="B",
        target_stage="B",
        template_kind=TEMPLATE_KIND_NLCD,
        firm_unshaded_x_ok=True,
        stage_a_report=True,
        stage_b_report=True,
        thread_id="stage_b_complete",
    )
    write_report(out_dir, report)
    return report
