# Copyright (c) 2026 Martial Systems LLC

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest
from rasterio.crs import CRS
from rasterio.warp import transform as rio_transform

from calumetmap.align import write_aligned
from calumetmap.codes import ZONE_SFHA, ZONE_UNSHADED_X
from calumetmap.config import (
    D_HEADLINE_N,
    HUC8,
    INDY_PLANT_NAMES,
    P_SFHA_CALIBRATED_NAME,
    P_SFHA_NODATA,
    P_SFHA_RAW_NAME,
)
from calumetmap.errors import GateError
from calumetmap.huc import load_huc
from calumetmap.stage_d import headline_five, run_stage_d, validate_d_report
from calumetmap.template import huc_geom_5070, write_nlcd_window
from calumetmap.tri import clip_to_huc, parse_tri_1a, refuse_indy_names

HUC = Path(__file__).resolve().parent / "fixtures" / "huc.geojson"


def test_refuse_indy_names() -> None:
    with pytest.raises(GateError, match="Indy plant"):
        refuse_indy_names([{"name": INDY_PLANT_NAMES[0]}])
    refuse_indy_names([{"name": "USS GARY WORKS"}])


def test_statewide_indy_row_is_dropped_by_huc_clip() -> None:
    text = (
        "5. ST,LATITUDE,LONGITUDE,FACILITY NAME,ON-SITE RELEASE TOTAL,CHEMICAL,UNIT OF MEASURE\n"
        "IN,39.77,-86.16,THURSDAY POOLS,10,LEAD,Pounds\n"
        "IN,41.58,-87.34,USS GARY WORKS,10,LEAD,Pounds\n"
    )
    by_fac, _budget = parse_tri_1a(text, year=2023)
    assert any("THURSDAY" in r["name"].upper() for r in by_fac.values())
    huc = load_huc(HUC)
    kept, n_out = clip_to_huc(by_fac.values(), huc)
    names = {r["name"].upper() for r in kept}
    assert "THURSDAY POOLS" not in names
    assert n_out >= 1


def test_tri_keeps_illinois_and_indiana() -> None:
    text = (
        "5. ST,LATITUDE,LONGITUDE,FACILITY NAME,ON-SITE RELEASE TOTAL,CHEMICAL,UNIT OF MEASURE\n"
        "IN,41.58,-87.34,USS GARY WORKS,10,LEAD,Pounds\n"
        "IL,41.60,-87.50,CALUMET IL MILL,4,LEAD,Pounds\n"
        "OH,39.96,-83.00,SOME OHIO PLANT,8,LEAD,Pounds\n"
    )
    by_fac, budget = parse_tri_1a(text, year=2023)
    names = {r["name"] for r in by_fac.values()}
    assert "USS GARY WORKS" in names
    assert "CALUMET IL MILL" in names
    assert "SOME OHIO PLANT" not in names
    assert budget["n_dropped_other_state"] == 1


def test_headline_five_sorts_by_pmax_and_keeps_mean() -> None:
    rows = [
        {"name": "A", "p_max": 0.2, "p_mean": 0.1, "on_site_release_lb": 100},
        {"name": "B", "p_max": 0.9, "p_mean": 0.4, "on_site_release_lb": 1},
        {"name": "C", "p_max": 0.8, "p_mean": 0.3, "on_site_release_lb": 50},
        {"name": "D", "p_max": 0.7, "p_mean": 0.2, "on_site_release_lb": 9},
        {"name": "E", "p_max": 0.6, "p_mean": 0.2, "on_site_release_lb": 9},
        {"name": "F", "p_max": 0.5, "p_mean": 0.1, "on_site_release_lb": 999},
    ]
    top = headline_five(rows)
    assert [r["name"] for r in top] == ["B", "C", "D", "E", "F"]
    assert all("p_mean" in r and r["p_mean"] is not None for r in top)
    assert len(top) == D_HEADLINE_N


def test_validate_d_refuses_raw_p_and_indy() -> None:
    base = {
        "p_definition": "P(sfha | hydro)",
        "p_source": P_SFHA_CALIBRATED_NAME,
        "expected_pounds_from_raw_p": False,
        "ofr_2008_covers_this_huc": False,
        "d1_n_unshaded_x": 5,
        "n_not_d1": 1,
        "n_tris_huc_year": 6,
        "d1_headline_rows": [
            {"name": "P{0}".format(i), "p_max": 0.2 + i / 10, "p_mean": 0.1, "on_site_release_lb": 1}
            for i in range(5)
        ],
    }
    validate_d_report(base)
    bad = dict(base)
    bad["expected_pounds_from_raw_p"] = True
    with pytest.raises(GateError, match="raw"):
        validate_d_report(bad)
    indy = dict(base)
    indy["d1_headline_rows"] = list(base["d1_headline_rows"])
    indy["d1_headline_rows"][0] = {
        "name": INDY_PLANT_NAMES[0],
        "p_max": 0.9,
        "p_mean": 0.2,
        "on_site_release_lb": 1,
    }
    with pytest.raises(GateError, match="Indy"):
        validate_d_report(indy)


def test_stage_d_overlay_calibrated_only(tmp_path: Path) -> None:
    huc = load_huc(HUC)
    geom = huc_geom_5070(huc)
    minx, _miny, _maxx, maxy = geom.bounds
    tmpl = write_nlcd_window(tmp_path / "nlcd.tif", west=minx, north=maxy, rows=80, cols=80)
    h, w = tmpl.height, tmpl.width
    cal = np.full((h, w), 0.05, dtype=np.float32)
    cal[:, :10] = 0.8
    raw = np.full((h, w), 0.4, dtype=np.float32)
    zone = np.full((h, w), ZONE_UNSHADED_X, dtype=np.uint8)
    zone[-5:, :] = ZONE_SFHA
    write_aligned(tmp_path / P_SFHA_CALIBRATED_NAME, tmpl, cal, dtype="float32", nodata=P_SFHA_NODATA)
    write_aligned(tmp_path / P_SFHA_RAW_NAME, tmpl, raw, dtype="float32", nodata=P_SFHA_NODATA)
    write_aligned(tmp_path / "zone_class.tif", tmpl, zone, dtype="uint8", nodata=255)
    lons, lats = rio_transform(
        CRS.from_epsg(5070),
        CRS.from_epsg(4269),
        [minx + 30 * i + 15 for i in range(6)],
        [maxy - 45] * 6,
    )
    csv_path = tmp_path / "tri.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        wcsv = csv.DictWriter(
            fh,
            fieldnames=["key", "name", "lat", "lon", "state", "huc", "year", "on_site_release_lb", "n_chem"],
        )
        wcsv.writeheader()
        for i, (lon, lat) in enumerate(zip(lons, lats)):
            wcsv.writerow(
                {
                    "key": "k{0}".format(i),
                    "name": "CALUMET MILL {0}".format(i),
                    "lat": lat,
                    "lon": lon,
                    "state": "IN" if i < 5 else "IL",
                    "huc": HUC8,
                    "year": 2023,
                    "on_site_release_lb": 10 + i,
                    "n_chem": 1,
                }
            )
    c_path = tmp_path / "c.json"
    c_path.write_text(
        json.dumps(
            {
                "stage": "C",
                "gate": "pass",
                "huc8": HUC8,
                "probabilities_calibrated": True,
                "p_sfha_calibrated_path": str(tmp_path / P_SFHA_CALIBRATED_NAME),
            }
        )
    )
    report = run_stage_d(
        huc_path=HUC,
        template_path=tmpl.path,
        interim_dir=tmp_path,
        out_dir=tmp_path / "out",
        stage_c_report_path=c_path,
        tri_csv=csv_path,
    )
    assert report["gate"] == "pass"
    assert report["p_source"] == P_SFHA_CALIBRATED_NAME
    assert report["n_tris_huc_year"] == 6
    assert report["d1_n_unshaded_x"] + report["n_not_d1"] == 6
    assert len(report["d1_headline_rows"]) == 5
    for row in report["d1_headline_rows"]:
        assert row["p_max"] is not None
        assert row["p_mean"] is not None
        assert "THURSDAY" not in row["name"].upper()
    assert (tmp_path / "out" / "d1_headline.csv").is_file()
    assert report["expected_pounds_from_raw_p"] is False
    assert "IL" in report["tri_states_present"] or "IN" in report["tri_states_present"]
