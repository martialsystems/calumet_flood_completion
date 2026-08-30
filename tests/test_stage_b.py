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
from calumetmap.config import (
    DEM_NODATA,
    HUC8,
    HYDRO_NODATA,
    NHD_FLOWLINE_WHERE,
    P_DEFINITION,
)
from calumetmap.errors import GateError
from calumetmap.huc import load_huc
from calumetmap.stage0 import run_stage0
from calumetmap.stage_b import refuse_nora_hand_copy, run_stage_b
from calumetmap.template import huc_geom_5070, write_nlcd_window

HUC = Path(__file__).resolve().parent / "fixtures" / "huc.geojson"


def _a_report(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "stage": "A",
                "gate": "pass",
                "huc8": HUC8,
                "firm_unshaded_x_ok": True,
                "p_definition": P_DEFINITION,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_nhd_flowline_where_keeps_artificial_path() -> None:
    assert "460" in NHD_FLOWLINE_WHERE
    assert "558" in NHD_FLOWLINE_WHERE


def test_refuse_nora_hand_copy() -> None:
    refuse_nora_hand_copy([Path("/tmp/calumet/hand.tif")])
    with pytest.raises(GateError, match="Nora HAND"):
        refuse_nora_hand_copy([Path("/tmp/white_river_stage_inundation/hand.tif")])
    with pytest.raises(GateError, match="Nora HAND"):
        refuse_nora_hand_copy([Path("/tmp/nora_live/hand.tif")])


def test_stage_b_refuses_fixture_template(tmp_path: Path) -> None:
    out = tmp_path / "s0"
    run_stage0(huc_path=HUC, out_dir=out)
    with pytest.raises(GateError, match="fixture"):
        run_stage_b(
            huc_path=HUC,
            template_path=out / "template.tif",
            interim_dir=tmp_path / "interim",
            out_dir=tmp_path / "out",
            stage_a_report_path=_a_report(tmp_path / "a.json"),
            flowline_features=[],
            waterbody_features=[],
            area_features=[],
        )


def test_stage_b_injected_hydro(tmp_path: Path) -> None:
    huc = load_huc(HUC)
    geom = huc_geom_5070(huc)
    minx, _miny, _maxx, maxy = geom.bounds
    tmpl = write_nlcd_window(
        tmp_path / "nlcd.tif", west=minx, north=maxy, rows=64, cols=64
    )
    dem = np.zeros((tmpl.height, tmpl.width), dtype=np.float32)
    for r in range(tmpl.height):
        dem[r, :] = 80.0 - r * 0.4
    write_aligned(tmp_path / "dem.tif", tmpl, dem, dtype="float32", nodata=DEM_NODATA)

    xs = [minx + 60, minx + 1800]
    ys = [maxy - 960, maxy - 960]
    lons, lats = rio_transform(CRS.from_epsg(5070), CRS.from_epsg(4269), xs, ys)
    flowline = {
        "type": "Feature",
        "properties": {"objectid": 1, "ftype": 460, "gnis_name": "Little Calumet River"},
        "geometry": {"type": "LineString", "coordinates": list(zip(lons, lats))},
    }
    lx, ly = rio_transform(
        CRS.from_epsg(5070),
        CRS.from_epsg(4269),
        [minx + 900, minx + 1200, minx + 1200, minx + 900, minx + 900],
        [maxy - 1200, maxy - 1200, maxy - 900, maxy - 900, maxy - 1200],
    )
    lake = {
        "type": "Feature",
        "properties": {"objectid": 2, "ftype": 390, "gnis_name": "Toy Lake"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [list(zip(lx, ly))],
        },
    }
    art = {
        "type": "Feature",
        "properties": {"objectid": 3, "ftype": 558, "gnis_name": "Little Calumet River"},
        "geometry": {
            "type": "LineString",
            "coordinates": list(
                zip(
                    *rio_transform(
                        CRS.from_epsg(5070),
                        CRS.from_epsg(4269),
                        [minx + 900, minx + 1200],
                        [maxy - 1050, maxy - 1050],
                    )
                )
            ),
        },
    }
    report = run_stage_b(
        huc_path=HUC,
        template_path=tmpl.path,
        interim_dir=tmp_path,
        out_dir=tmp_path / "out",
        stage_a_report_path=_a_report(tmp_path / "a.json"),
        flowline_features=[flowline, art],
        waterbody_features=[lake],
        area_features=[],
    )
    assert report["gate"] == "pass"
    assert report["stage"] == "B"
    assert report["huc8"] == HUC8
    assert report["twi_finite_on_dem_valid"] is True
    assert report["hand_is_flow_path"] is True
    assert report["stage_c_started"] is False
    assert report["nora_hand_copied"] is False
    assert report["hand_nodata_filled_with_zero"] is False
    assert report["n_stream_cells"] > 0
    assert report["n_waterbody_cells"] > 0
    assert report["flowline_ftype_counts"].get("460", 0) >= 1
    assert report["flowline_ftype_counts"].get("558", 0) >= 1
    for name in ("twi", "hand", "slope", "dist_flowline", "dist_waterbody"):
        path = tmp_path / "{0}.tif".format(name)
        assert path.is_file()
        with rasterio.open(path) as src:
            assert src.crs.to_epsg() == 5070
            arr = src.read(1)
        if name == "twi":
            finite = arr[arr != HYDRO_NODATA]
            assert finite.size > 0
            assert np.isfinite(finite).all()
        if name == "hand":
            finite = arr[arr != HYDRO_NODATA]
            assert finite.size > 0
            assert np.nanmin(finite) >= 0.0
        if name == "dist_flowline":
            assert (arr == 0).any()
    assert (tmp_path / "out" / "stage_b_report.json").is_file()
