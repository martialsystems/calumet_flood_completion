# Copyright (c) 2026 Martial Systems LLC

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.crs import CRS
from rasterio.warp import transform as rio_transform

from calumetmap.align import write_aligned
from calumetmap.calibrate import calibrate_leave_one_huc10, calibrate_oof_pooled
from calumetmap.codes import ZONE_FLOODWAY, ZONE_SFHA, ZONE_UNSHADED_X
from calumetmap.config import (
    C_HGB_LEARNING_RATE,
    C_HGB_MAX_DEPTH,
    C_HGB_MAX_ITER,
    DEM_NODATA,
    DIST_NODATA,
    HAND_NODATA_RULE,
    HUC8,
    HYDRO_NODATA,
    P_DEFINITION,
    P_SFHA_CALIBRATED_NAME,
    P_SFHA_NODATA,
    P_SFHA_RAW_NAME,
    STAGE_C_FEATURES,
)
from calumetmap.errors import GateError
from calumetmap.huc import load_huc
from calumetmap.huc10 import train_test_halo
from calumetmap.stage0 import run_stage0
from calumetmap.stage_c import hand_defined, require_floodway_in_sfha, run_stage_c, stratify_sample
from calumetmap.template import huc_geom_5070, write_nlcd_window

HUC = Path(__file__).resolve().parent / "fixtures" / "huc.geojson"


def test_no_upper_white_booster_hyperparams() -> None:
    assert C_HGB_MAX_DEPTH != 4 or C_HGB_MAX_ITER != 200 or C_HGB_LEARNING_RATE != 0.08
    req = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text()
    assert "xgboost" not in req.lower()


def test_hand_defined_excludes_nodata() -> None:
    inside = np.ones((3, 3), dtype=bool)
    hand = np.zeros((3, 3), dtype=np.float32)
    hand[1, 1] = HYDRO_NODATA
    hand[0, 0] = np.nan
    d = hand_defined(hand, inside)
    assert not d[1, 1]
    assert not d[0, 0]
    assert d[2, 2]


def test_floodway_must_be_sfha() -> None:
    inside = np.ones((3, 3), dtype=bool)
    zone = np.zeros((3, 3), dtype=np.uint8)
    sfha = np.zeros((3, 3), dtype=np.uint8)
    zone[1, 1] = ZONE_FLOODWAY
    sfha[1, 1] = 1
    require_floodway_in_sfha(zone, sfha, inside)
    sfha[1, 1] = 0
    with pytest.raises(GateError, match="floodway"):
        require_floodway_in_sfha(zone, sfha, inside)


def test_halo_excludes_test_and_ring() -> None:
    huc10 = np.zeros((5, 5), dtype=np.uint16)
    huc10[:, :3] = 1
    huc10[:, 3:] = 2
    eligible = np.ones((5, 5), dtype=bool)
    train, test, halo = train_test_halo(huc10, 1, eligible)
    assert test[0, 0]
    assert not train[0, 0]
    assert halo[0, 3]
    assert not train[0, 3]


def test_stratify_keeps_all_positives() -> None:
    pos = np.zeros((10, 10), dtype=bool)
    pos[0, :5] = True
    neg = ~pos
    near = np.zeros_like(pos)
    near[9, :8] = True
    rng = np.random.default_rng(0)
    r, c = stratify_sample(pos=pos, neg=neg, unshaded_near=near, ratio=2.0, rng=rng)
    y = pos[r, c]
    assert int(y.sum()) == 5
    assert r.size == 5 + 10


def test_isotonic_drops_mean_keeps_rank() -> None:
    p = np.array([[0.75, 0.40, 0.75, 0.40], [0.75, 0.40, 0.75, 0.40]], dtype=np.float32)
    y = np.array([[1, 0, 1, 0], [1, 0, 1, 0]], dtype=np.uint8)
    huc10 = np.array([[1, 1, 2, 2], [1, 1, 2, 2]], dtype=np.uint16)
    valid = np.ones_like(y, dtype=bool)
    cal = calibrate_leave_one_huc10(p, y, huc10, valid)
    assert cal[0, 0] > cal[0, 1]
    assert float(np.mean(cal)) < float(np.mean(p))


def test_pooled_isotonic_preserves_rank() -> None:
    p = np.array([[0.9, 0.2], [0.8, 0.1]], dtype=np.float32)
    y = np.array([[1, 0], [1, 0]], dtype=np.uint8)
    valid = np.ones_like(y, dtype=bool)
    cal = calibrate_oof_pooled(p, y, valid)
    assert cal[0, 0] >= cal[1, 0] >= cal[0, 1] >= cal[1, 1]


def test_stage_c_refuses_fixture(tmp_path: Path) -> None:
    out = tmp_path / "s0"
    run_stage0(huc_path=HUC, out_dir=out)
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps({"stage": "A", "gate": "pass", "firm_unshaded_x_ok": True}))
    b.write_text(
        json.dumps(
            {
                "stage": "B",
                "gate": "pass",
                "hand_nodata_filled_with_zero": False,
                "hand_nodata_rule": HAND_NODATA_RULE,
            }
        )
    )
    with pytest.raises(GateError, match="fixture"):
        run_stage_c(
            huc_path=HUC,
            template_path=out / "template.tif",
            interim_dir=tmp_path,
            out_dir=tmp_path / "out",
            raw_dir=tmp_path / "raw",
            stage_a_report_path=a,
            stage_b_report_path=b,
            huc10_features=[],
        )


def test_stage_c_oof_isotonic_and_hand_nodata(tmp_path: Path) -> None:
    huc = load_huc(HUC)
    geom = huc_geom_5070(huc)
    minx, _miny, _maxx, maxy = geom.bounds
    tmpl = write_nlcd_window(
        tmp_path / "nlcd.tif", west=minx, north=maxy, rows=80, cols=80
    )
    h, w = tmpl.height, tmpl.width
    hand = np.full((h, w), 20.0, dtype=np.float32)
    hand[h // 2 :, :] = 1.0
    hand[0, 0] = HYDRO_NODATA
    sfha = np.zeros((h, w), dtype=np.uint8)
    sfha[h // 2 :, :] = 1
    zone = np.full((h, w), ZONE_UNSHADED_X, dtype=np.uint8)
    zone[h // 2 :, :] = ZONE_SFHA
    zone[h // 2, :3] = ZONE_FLOODWAY
    sfha[h // 2, :3] = 1
    slope = np.full((h, w), 0.02, dtype=np.float32)
    twi = np.where(hand < 5, 12.0, 6.0).astype(np.float32)
    dist_fl = np.where(hand < 5, 30.0, 400.0).astype(np.float32)
    dist_wb = np.full((h, w), 800.0, dtype=np.float32)
    dist_wb[h // 2, w // 2] = 0.0
    for name, arr, nod in (
        ("hand", hand, HYDRO_NODATA),
        ("slope", slope, HYDRO_NODATA),
        ("twi", twi, HYDRO_NODATA),
        ("dist_flowline", dist_fl, DIST_NODATA),
        ("dist_waterbody", dist_wb, DIST_NODATA),
        ("sfha", sfha, 255),
        ("zone_class", zone, 255),
    ):
        write_aligned(tmp_path / "{0}.tif".format(name), tmpl, arr, dtype=arr.dtype.name, nodata=nod)
    write_aligned(
        tmp_path / "dem.tif",
        tmpl,
        np.full((h, w), 200.0, dtype=np.float32),
        dtype="float32",
        nodata=DEM_NODATA,
    )
    west_lon, north_lat = rio_transform(
        CRS.from_epsg(5070), CRS.from_epsg(4269), [minx], [maxy]
    )
    east_lon, south_lat = rio_transform(
        CRS.from_epsg(5070),
        CRS.from_epsg(4269),
        [minx + w * 30],
        [maxy - h * 30],
    )
    mid_lon = (west_lon[0] + east_lon[0]) / 2
    left = {
        "type": "Feature",
        "properties": {"huc10": "{0}01".format(HUC8), "name": "Left"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [west_lon[0], south_lat[0]],
                    [mid_lon, south_lat[0]],
                    [mid_lon, north_lat[0]],
                    [west_lon[0], north_lat[0]],
                    [west_lon[0], south_lat[0]],
                ]
            ],
        },
    }
    right = {
        "type": "Feature",
        "properties": {"huc10": "{0}02".format(HUC8), "name": "Right"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [mid_lon, south_lat[0]],
                    [east_lon[0], south_lat[0]],
                    [east_lon[0], north_lat[0]],
                    [mid_lon, north_lat[0]],
                    [mid_lon, south_lat[0]],
                ]
            ],
        },
    }
    a_path = tmp_path / "stage_a_report.json"
    b_path = tmp_path / "stage_b_report.json"
    a_path.write_text(
        json.dumps({"stage": "A", "gate": "pass", "huc8": HUC8, "firm_unshaded_x_ok": True})
    )
    b_path.write_text(
        json.dumps(
            {
                "stage": "B",
                "gate": "pass",
                "huc8": HUC8,
                "hand_nodata_filled_with_zero": False,
                "hand_nodata_rule": HAND_NODATA_RULE,
                "nora_hand_copied": False,
            }
        )
    )
    report = run_stage_c(
        huc_path=HUC,
        template_path=tmpl.path,
        interim_dir=tmp_path,
        out_dir=tmp_path / "out",
        raw_dir=tmp_path / "raw",
        stage_a_report_path=a_path,
        stage_b_report_path=b_path,
        huc10_features=[left, right],
    )
    assert report["gate"] == "pass"
    assert report["p_definition"] == P_DEFINITION
    assert report["probabilities_calibrated"] is True
    assert report["raw_raster_kept"] is True
    assert report["method_calibrated"] in {
        "isotonic_leave_one_huc10_out",
        "isotonic_oof_pooled",
    }
    assert report["upper_white_booster_copied"] is False
    assert report["fim_started"] is False
    assert report["industrial_points_started"] is False
    assert report["pr_auc"] > report["pr_auc_baseline"]
    assert "hand_negated_pr_auc" in report
    assert report["n_huc10"] == 2
    assert report["halo_pixels"] == 1
    assert list(report["features"]) == list(STAGE_C_FEATURES)
    assert (tmp_path / P_SFHA_RAW_NAME).is_file()
    assert (tmp_path / P_SFHA_CALIBRATED_NAME).is_file()
    with rasterio.open(tmp_path / P_SFHA_RAW_NAME) as src:
        raw = src.read(1)
    with rasterio.open(tmp_path / P_SFHA_CALIBRATED_NAME) as src:
        cal = src.read(1)
    assert raw[0, 0] == P_SFHA_NODATA
    assert cal[0, 0] == P_SFHA_NODATA
    assert (tmp_path / "out" / "stage_c_report.json").is_file()
