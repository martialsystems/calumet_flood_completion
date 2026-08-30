# Copyright (c) 2026 Martial Systems LLC
import json
from pathlib import Path

import pytest

from calumetmap.config import HUC8, PARENT_HUC8, TEMPLATE_CRS, TEMPLATE_KIND_NLCD, TEMPLATE_RES_M
from calumetmap.errors import EmptyHucError, GateError
from calumetmap.huc import load_huc
from calumetmap.stage0 import run_stage0

HUC = Path(__file__).resolve().parent / "fixtures" / "huc.geojson"


def test_stage0_fixture_writes_report(tmp_path: Path) -> None:
    out = tmp_path / "stage0"
    report = run_stage0(huc_path=HUC, out_dir=out)
    assert report["gate"] == "pass"
    assert report["stage"] == "0"
    assert report["huc8"] == HUC8
    assert report["unit"] == "pixel"
    assert report["p_definition"] == "P(sfha | hydro)"
    assert report["template_crs"] == TEMPLATE_CRS
    assert report["template_res_m"] == TEMPLATE_RES_M
    assert report["template_kind"] == "fixture"
    assert report["ofr_2008_covers_this_huc"] is False
    assert report["indy_plants_copied"] is False
    assert (out / "stage0_report.json").is_file()
    assert (out / "template.tif").is_file()


def test_stage0_nlcd_kind_requires_path(tmp_path: Path) -> None:
    with pytest.raises(GateError, match="path is required"):
        run_stage0(
            huc_path=HUC,
            out_dir=tmp_path / "stage0",
            template_kind=TEMPLATE_KIND_NLCD,
        )


def test_stage0_refuses_nlcd_kind_on_fixture_grid(tmp_path: Path) -> None:
    out = tmp_path / "stage0"
    run_stage0(huc_path=HUC, out_dir=out)
    tif = out / "template.tif"
    with pytest.raises(GateError, match="fixture grid"):
        run_stage0(
            huc_path=HUC,
            out_dir=tmp_path / "stage0b",
            template_path=tif,
            template_kind=TEMPLATE_KIND_NLCD,
        )


def test_refuses_upper_white_huc(tmp_path: Path) -> None:
    bad = tmp_path / "white.geojson"
    bad.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {"type": "name", "properties": {"name": "EPSG:4269"}},
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"huc8": PARENT_HUC8},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-86.3, 39.9], [-86.0, 39.9], [-86.0, 39.7], [-86.3, 39.7], [-86.3, 39.9]]],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(GateError, match="Upper White"):
        load_huc(bad)
