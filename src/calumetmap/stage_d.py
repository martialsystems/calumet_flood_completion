# Copyright (c) 2026 Martial Systems LLC
"""Stage D: TRI points on calibrated P. Five rows by window-max. No Indy names."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.warp import transform as rio_transform

from calumetmap.align import require_live_template, template_fingerprint
from calumetmap.codes import ZONE_CLASS_NAME, ZONE_FLOODWAY, ZONE_SFHA, d1_eligible
from calumetmap.config import (
    D_BUFFER_RADIUS_CELLS,
    D_HEADLINE_N,
    D1_HEADER,
    FIRM_LIVE_MIN_HEIGHT,
    FIRM_LIVE_MIN_WIDTH,
    HUC8,
    INDY_PLANT_NAMES,
    LOCKED_TRANSFORM_SHA256,
    P_SFHA_CALIBRATED_NAME,
    P_SFHA_NODATA,
    P_SFHA_RAW_NAME,
    TEMPLATE_CRS,
    TEMPLATE_KIND_NLCD,
    TEMPLATE_RES_M,
    TRI_STATES,
    VECTOR_CRS,
)
from calumetmap.errors import GateError
from calumetmap.huc import load_huc
from calumetmap.report import build_stage_d_report, write_report
from calumetmap.stage_b import refuse_nora_hand_copy
from calumetmap.template import inspect_template
from calumetmap.tri import fetch_tri_in_huc, load_tri_csv, refuse_indy_names, write_facilities_csv

try:
    from calumetforge.gate import require_claims, require_huc, require_stage
except ImportError:  # pragma: no cover

    def require_claims(**kwargs):
        del kwargs

    def require_huc(**kwargs):
        del kwargs

    def require_stage(**kwargs):
        del kwargs


def _load_report(path: Path, stage: str) -> dict[str, Any]:
    if not path.is_file():
        raise GateError("Stage {0} report missing: {1}".format(stage, path))
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("stage") != stage or obj.get("gate") != "pass":
        raise GateError("Stage {0} report is not a passing artifact".format(stage))
    return obj


def buffer_p_stats(
    p: np.ndarray,
    row: int,
    col: int,
    *,
    radius: int,
    nodata: float,
) -> tuple[float | None, float | None, int]:
    h, w = p.shape
    r0 = max(0, row - radius)
    r1 = min(h, row + radius + 1)
    c0 = max(0, col - radius)
    c1 = min(w, col + radius + 1)
    win = p[r0:r1, c0:c1]
    ok = np.isfinite(win) & (win != nodata)
    if not ok.any():
        return None, None, 0
    vals = win[ok]
    return float(vals.max()), float(vals.mean()), int(ok.sum())


def buffer_p_argmax(
    p: np.ndarray,
    row: int,
    col: int,
    *,
    radius: int,
    nodata: float,
) -> tuple[int, int] | None:
    h, w = p.shape
    r0 = max(0, row - radius)
    r1 = min(h, row + radius + 1)
    c0 = max(0, col - radius)
    c1 = min(w, col + radius + 1)
    win = p[r0:r1, c0:c1]
    ok = np.isfinite(win) & (win != nodata)
    if not ok.any():
        return None
    filled = np.where(ok, win, -np.inf)
    wr, wc = np.unravel_index(int(np.argmax(filled)), win.shape)
    return r0 + int(wr), c0 + int(wc)


def classify_pmax_cell(
    *,
    office_row: int,
    office_col: int,
    max_row: int,
    max_col: int,
    zone_code: int,
    dist_flowline: float | None,
    dist_waterbody: float | None,
) -> str:
    if max_row == office_row and max_col == office_col:
        return "office_pixel"
    if (
        dist_waterbody == 0
        or dist_flowline == 0
        or zone_code in (ZONE_SFHA, ZONE_FLOODWAY)
    ):
        return "adjacent_hydro_cell"
    return "neighboring_land_cell"


def headline_five(d1_rows: list[dict[str, Any]], *, n: int = D_HEADLINE_N) -> list[dict[str, Any]]:
    """Top n D1 sites by window p_max, then pounds. p_mean stays on the same row."""
    scored = [r for r in d1_rows if r.get("p_max") is not None and r.get("p_mean") is not None]
    scored.sort(
        key=lambda r: (float(r["p_max"]), float(r["on_site_release_lb"])),
        reverse=True,
    )
    take = scored[:n]
    if len(d1_rows) >= n and len(take) != n:
        raise GateError("Stage D headline needs {0} scored D1 rows".format(n))
    for row in take:
        for key in ("name", "p_max", "p_mean", "on_site_release_lb"):
            if key not in row or row[key] is None:
                raise GateError("headline row missing {0}".format(key))
    refuse_indy_names(take)
    return take


def validate_d_report(obj: Mapping[str, Any]) -> None:
    if obj.get("p_definition") != "P(sfha | hydro)":
        raise GateError("Stage D p_definition must be P(sfha | hydro)")
    p_source = str(obj.get("p_source") or "")
    if P_SFHA_CALIBRATED_NAME not in p_source:
        raise GateError("Stage D p_source must be p_sfha_calibrated.tif")
    if obj.get("expected_pounds_from_raw_p"):
        raise GateError("Stage D must not ship sum(P*lb) from the raw grid")
    if "share_in_sfha" in obj:
        raise GateError("Stage D must not print share_in_sfha as this tree's occupancy")
    if obj.get("ofr_2008_covers_this_huc"):
        raise GateError("OFR 2008 is not a Calumet mask")
    try:
        n_d1 = int(obj["d1_n_unshaded_x"])
        n_not = int(obj["n_not_d1"])
        n_all = int(obj["n_tris_huc_year"])
    except (TypeError, ValueError, KeyError) as exc:
        raise GateError("Stage D d1/not_d1/n_tris must be integers") from exc
    if n_d1 + n_not != n_all:
        raise GateError("d1_n_unshaded_x + n_not_d1 must equal n_tris_huc_year")
    rows = obj.get("d1_headline_rows")
    if not isinstance(rows, list):
        raise GateError("Stage D must list d1_headline_rows with p_max and p_mean")
    want = min(D_HEADLINE_N, n_d1)
    if len(rows) != want:
        raise GateError("Stage D headline must have {0} rows, got {1}".format(want, len(rows)))
    for row in rows:
        if not isinstance(row, dict):
            raise GateError("d1_headline_rows entries must be objects")
        for key in ("name", "p_max", "p_mean", "on_site_release_lb"):
            if key not in row:
                raise GateError("d1_headline_rows missing {0}".format(key))
        name = str(row["name"]).upper()
        for plant in INDY_PLANT_NAMES:
            if plant.upper() in name:
                raise GateError("headline copied Indy plant {0}".format(plant))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def run_stage_d(
    *,
    huc_path: Path,
    template_path: Path,
    interim_dir: Path,
    out_dir: Path,
    stage_c_report_path: Path,
    tri_csv: Path | None = None,
    get_bytes=None,
) -> dict:
    require_claims()
    refuse_nora_hand_copy([huc_path, template_path, interim_dir, out_dir, stage_c_report_path])
    c_report = _load_report(stage_c_report_path, "C")
    if not c_report.get("probabilities_calibrated"):
        raise GateError("Stage D needs isotonic calibrated P")
    cal_name = Path(str(c_report.get("p_sfha_calibrated_path") or P_SFHA_CALIBRATED_NAME)).name
    if cal_name != P_SFHA_CALIBRATED_NAME:
        raise GateError("Stage D p_source must be p_sfha_calibrated.tif")
    huc = load_huc(huc_path)
    require_huc(huc8=huc.huc8, parent_huc=False)
    template = inspect_template(template_path, kind=TEMPLATE_KIND_NLCD)
    require_live_template(template)
    fp = template_fingerprint(template)
    live = template.width >= FIRM_LIVE_MIN_WIDTH and template.height >= FIRM_LIVE_MIN_HEIGHT
    a_fp = (c_report.get("template_fingerprint") or {}).get("transform_sha256")
    if a_fp == LOCKED_TRANSFORM_SHA256 and fp["transform_sha256"] != LOCKED_TRANSFORM_SHA256:
        raise GateError("Stage D requires the locked template")
    require_stage(
        current_stage="C",
        target_stage="D",
        template_kind=TEMPLATE_KIND_NLCD,
        firm_unshaded_x_ok=True,
        stage_a_report=True,
        stage_b_report=True,
        probabilities_calibrated=True,
        sample_p=True,
        thread_id="stage_d",
    )

    p_path = interim_dir / P_SFHA_CALIBRATED_NAME
    raw_path = interim_dir / P_SFHA_RAW_NAME
    if not p_path.is_file():
        raise GateError("missing {0}".format(P_SFHA_CALIBRATED_NAME))
    if not raw_path.is_file():
        raise GateError("uncalibrated p_sfha.tif must remain on disk")
    with rasterio.open(p_path) as src:
        p = src.read(1)
        p_crs = src.crs
        p_transform = src.transform
    with rasterio.open(raw_path) as src:
        raw = src.read(1)
    if np.array_equal(p, raw):
        raise GateError("calibrated P equals raw P; overlay would use uncalibrated scores")
    with rasterio.open(interim_dir / "zone_class.tif") as src:
        zone = src.read(1)
    hydro = None
    if (interim_dir / "dist_flowline.tif").is_file():
        with rasterio.open(interim_dir / "dist_flowline.tif") as src:
            dist_fl = src.read(1)
        with rasterio.open(interim_dir / "dist_waterbody.tif") as src:
            dist_wb = src.read(1)
        hydro = (dist_fl, dist_wb)

    dest_csv = interim_dir / "tri_huc.csv"
    if tri_csv is not None:
        facilities = load_tri_csv(tri_csv)
        budget = {"n_tris_huc_year": len(facilities), "from_csv": True, "reporting_year": facilities[0]["year"]}
        write_facilities_csv(dest_csv, facilities)
    else:
        facilities, budget = fetch_tri_in_huc(huc, dest_csv, get_bytes=get_bytes)
    refuse_indy_names(facilities)
    n_tris = len(facilities)
    if n_tris == 0:
        raise GateError("no TRI facilities in HUC {0}".format(HUC8))

    allowed = {s.upper() for s in TRI_STATES}
    radius = D_BUFFER_RADIUS_CELLS
    rows_out: list[dict[str, Any]] = []
    for rec in facilities:
        if rec.get("huc") not in ("", HUC8):
            raise GateError("facility {0} huc={1}".format(rec.get("key"), rec.get("huc")))
        st = str(rec.get("state") or "").upper()
        if st and st not in allowed:
            raise GateError("facility {0} state={1} not in {2}".format(rec.get("key"), st, TRI_STATES))
        xs, ys = rio_transform(
            CRS.from_epsg(VECTOR_CRS),
            p_crs or CRS.from_epsg(TEMPLATE_CRS),
            [rec["lon"]],
            [rec["lat"]],
        )
        row, col = rasterio.transform.rowcol(p_transform, xs[0], ys[0])
        zcode = int(zone[row, col]) if 0 <= row < zone.shape[0] and 0 <= col < zone.shape[1] else 255
        zname = ZONE_CLASS_NAME.get(zcode, "other")
        p_max, p_mean, n_buf = buffer_p_stats(
            p, int(row), int(col), radius=radius, nodata=P_SFHA_NODATA
        )
        arg = buffer_p_argmax(p, int(row), int(col), radius=radius, nodata=P_SFHA_NODATA)
        p_max_note = "unscored"
        p_max_dr = p_max_dc = None
        p_max_zone = None
        if arg is not None:
            pr, pc = arg
            p_max_dr, p_max_dc = int(pr - row), int(pc - col)
            p_max_zone = ZONE_CLASS_NAME.get(int(zone[pr, pc]), "other")
            if hydro is not None:
                dfl, dwb = hydro
                p_max_note = classify_pmax_cell(
                    office_row=int(row),
                    office_col=int(col),
                    max_row=pr,
                    max_col=pc,
                    zone_code=int(zone[pr, pc]),
                    dist_flowline=float(dfl[pr, pc]),
                    dist_waterbody=float(dwb[pr, pc]),
                )
            elif p_max_dr == 0 and p_max_dc == 0:
                p_max_note = "office_pixel"
            else:
                p_max_note = "neighboring_land_cell"
        rows_out.append(
            {
                "key": rec["key"],
                "name": rec["name"],
                "lat": rec["lat"],
                "lon": rec["lon"],
                "huc": HUC8,
                "state": st,
                "year": rec["year"],
                "on_site_release_lb": rec["on_site_release_lb"],
                "zone_class": zname,
                "p_max": p_max,
                "p_mean": p_mean,
                "p_max_note": p_max_note,
                "p_max_dr": p_max_dr,
                "p_max_dc": p_max_dc,
                "p_max_zone_class": p_max_zone,
                "n_buffer_cells": n_buf,
                "buffer_radius_cells": radius,
                "buffer_m": radius * TEMPLATE_RES_M,
                "d1_eligible": bool(d1_eligible(zname) and p_max is not None),
            }
        )

    d1_rows = [r for r in rows_out if r["d1_eligible"]]
    not_d1 = [r for r in rows_out if not r["d1_eligible"]]
    not_d1_zones: dict[str, int] = {}
    for r in not_d1:
        not_d1_zones[r["zone_class"]] = not_d1_zones.get(r["zone_class"], 0) + 1
    headline = headline_five(d1_rows)
    states_present = sorted({r["state"] for r in rows_out if r["state"]})
    if "IN" not in {s.upper() for s in states_present} and live:
        raise GateError("Stage D TRI in this HUC must include Indiana")

    fields = [
        "key",
        "name",
        "lat",
        "lon",
        "huc",
        "state",
        "year",
        "on_site_release_lb",
        "zone_class",
        "p_max",
        "p_mean",
        "p_max_note",
        "p_max_dr",
        "p_max_dc",
        "p_max_zone_class",
        "n_buffer_cells",
        "d1_eligible",
    ]
    headline_fields = [
        "name",
        "on_site_release_lb",
        "p_max",
        "p_mean",
        "p_max_note",
        "p_max_zone_class",
        "state",
        "year",
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(out_dir / "d1.csv", d1_rows, fields)
    _write_csv(out_dir / "facilities.csv", rows_out, fields)
    _write_csv(out_dir / "d1_headline.csv", headline, headline_fields)
    write_facilities_csv(interim_dir / "tri_huc.csv", facilities)

    extra = {
        "template_fingerprint": fp,
        "d1_header": D1_HEADER,
        "d1_zone_class": "unshaded_x",
        "p_source": P_SFHA_CALIBRATED_NAME,
        "p_source_raw_kept": P_SFHA_RAW_NAME,
        "expected_pounds_from_raw_p": False,
        "headline_p": "p_max",
        "headline_n": D_HEADLINE_N,
        "headline_rule": "top_{0}_d1_by_p_max_then_pounds; p_mean on the same row".format(
            D_HEADLINE_N
        ),
        "buffer_radius_cells": radius,
        "buffer_m": radius * TEMPLATE_RES_M,
        "n_tris_huc_year": n_tris,
        "tri": budget,
        "d1_n_unshaded_x": len(d1_rows),
        "n_not_d1": len(not_d1),
        "not_d1_zone_class": not_d1_zones,
        "not_d1_rows": [
            {
                "name": r["name"],
                "zone_class": r["zone_class"],
                "state": r["state"],
                "p_max": r["p_max"],
                "p_mean": r["p_mean"],
                "on_site_release_lb": r["on_site_release_lb"],
            }
            for r in not_d1
        ],
        "d1_reading": (
            "buffer-max is a 30 m edge of the 120 m window; "
            "buffer-mean is the site footprint"
        ),
        "d1_headline_rows": [
            {
                "name": r["name"],
                "on_site_release_lb": r["on_site_release_lb"],
                "p_max": r["p_max"],
                "p_mean": r["p_mean"],
                "p_max_note": r["p_max_note"],
                "p_max_zone_class": r.get("p_max_zone_class"),
                "state": r["state"],
                "year": r["year"],
            }
            for r in headline
        ],
        "tri_states": list(TRI_STATES),
        "tri_states_present": states_present,
        "indy_plants_copied": False,
        "fim_started": False,
        "ofr_2008_covers_this_huc": False,
        "probabilities_calibrated": True,
    }
    report = build_stage_d_report(huc, template, extra=extra)
    validate_d_report(report)
    require_stage(
        current_stage="D",
        target_stage="D",
        template_kind=TEMPLATE_KIND_NLCD,
        firm_unshaded_x_ok=True,
        stage_a_report=True,
        stage_b_report=True,
        probabilities_calibrated=True,
        sample_p=True,
        thread_id="stage_d_complete",
    )
    write_report(out_dir, report)
    return report
